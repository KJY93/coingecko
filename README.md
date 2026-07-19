# gecko

A crypto market-data backend. It polls CoinGecko for the top coins, runs the
data through a RabbitMQ pipeline, and stores the price history in MongoDB so you
can query it.

Heads up: a bunch of this is more than a project this size actually needs. That
was kind of the point — I wanted to run into the real problems, not avoid them.

## Why I built it

At work I'd dealt with RabbitMQ code that only did the happy path. Declare a
queue, publish, consume, done. It worked until it didn't. Some of the stuff that
was wrong with it:

- it acked messages the moment they arrived, before doing anything with them. So
  if the consumer died mid-processing, the message was just gone.
- no idempotency. if a message came through twice you'd get duplicate data.
- when publishing failed it would tear down the whole connection and retry
  blindly.
- the queue was set to drop/expire messages when it got full, and there was
  nowhere for those dropped messages to go. they just vanished.
- there was a global variable holding the "current" timestamp, which two
  messages could overwrite on each other.

I wanted to actually understand this stuff instead of copy-pasting a fix, so I
decided to build my own version that handles all of it properly.

CoinGecko has a free API, so a little market-data / trading-style platform
seemed like a good thing to build around — there's a real data stream to pull
in, and it fits the producer/consumer thing I wanted to learn.

Two goals really:

1. understand the messaging patterns the bad code skipped — at-least-once
   delivery, idempotency, retries, dead-letter queues, publisher confirms,
   graceful shutdown, scaling.
2. see what else a non-toy backend involves — auth, tests, error handling,
   logging, deployment.

The design decisions section is basically my notes on what I figured out and
why I did things the way I did.

## What it does

- polls CoinGecko on a schedule for the top ~500 coins.
- publishes that data to RabbitMQ (split into a few paginated messages).
- a separate consumer worker transforms it and writes it to MongoDB as price
  history over time.
- has a REST API to query coins and their history, behind JWT auth.
- Redis for caching + rate limiting.

## Architecture

```
                 ┌──────────────┐
   CoinGecko ───▶│  Scheduler   │  (APScheduler, polls on an interval)
     API         │ poll_market_ │
                 │   data()     │
                 └──────┬───────┘
                        │ publishes paginated market data
                        ▼
                 ┌──────────────┐        ┌──────────────────┐
                 │ market_data  │        │  Retry queue     │
                 │  exchange    │        │  (TTL = 5s delay)│
                 └──────┬───────┘        └────────┬─────────┘
                        ▼                          │ on TTL expiry,
                 ┌──────────────┐                  │ bounces back
                 │ market_data  │◀─────────────────┘
                 │    queue     │
                 └──────┬───────┘
                        │ consumed by
                        ▼
                 ┌──────────────┐   max retries hit      ┌─────────────┐
                 │  Consumer    │───────────────────────▶│  DLX → DLQ  │
                 │ worker       │   nack(requeue=False)   │ (quarantine)│
                 │ (transform + │                         └─────────────┘
                 │  upsert)     │
                 └──────┬───────┘
                        │ idempotent upsert
                        ▼
                 ┌──────────────┐         ┌──────────────┐
                 │   MongoDB    │◀────────│  FastAPI     │  (REST + JWT)
                 │ (price       │  reads  │  endpoints   │
                 │  history)    │         └──────────────┘
                 └──────────────┘
```

## Stack

- FastAPI
- MongoDB (async PyMongo)
- RabbitMQ (aio-pika)
- Redis
- APScheduler
- Docker Compose for local infra (Mongo + Redis + RabbitMQ)
- pytest
- Python 3.13

## Layout

```
app/
├── api/              # routers (coins, auth)
├── core/             # config, security (JWT), logging, rate limiter
├── models/           # pydantic models
├── scheduler/        # APScheduler + the polling job (producer)
├── services/
│   ├── connections/  # mongodb + rabbitmq client
│   └── repositories/ # data access
└── consumer.py       # the rabbitmq consumer worker (run separately)
main.py               # entrypoint + lifespan
tests/
docker-compose.yml
```

## About the queue

To be clear, for gecko's traffic — 500 coins every few minutes — RabbitMQ is
total overkill. You could just poll and write to Mongo directly. But the whole
reason it's here is the failure handling. The queue is what makes you deal with
retries, duplicates, poison messages and scaling instead of pretending they
won't happen, which is exactly what the code that got me started did.

The producer (scheduler) and the consumer (worker) are separate. The producer
just publishes. The consumer runs on its own and you can run more than one of
them.

## Design decisions

### Idempotency

RabbitMQ delivers at-least-once, so a message can show up more than once (say
the consumer crashes after writing but before acking). A plain insert would just
duplicate the record.

So I store with an upsert keyed on `(coingecko_id, recorded_at)` — `bulk_write`
with `UpdateOne(..., upsert=True)`. Process the same message five times and you
still end up with one record.

The part I didn't catch at first: this only works if `recorded_at` is set when
the data is *published*, not when it's *consumed*. If the consumer set it with
`datetime.now()`, a redelivery a few seconds later gets a different timestamp,
which means a different key, which means it duplicates anyway. So the producer
sets the timestamp and ships it inside the message. That's the bit that made
idempotency actually work instead of just looking like it did.

(Also worth noting — this is basically the same class of bug as the global
timestamp variable I mentioned up top. Tie the timestamp to the message, not to
shared state.)

### Retries, then dead-letter

The lazy way to handle a failure is `nack(requeue=True)`, which just drops the
message back on the queue where it instantly fails again. Tight loop, pins the
CPU. A poison message does this forever.

What I do instead:

- on failure, republish the message to a retry queue. that queue has a 5s TTL
  and dead-letters back to the main queue when the TTL runs out — so the message
  waits 5s, then gets retried. a counter in the headers caps it at 3 tries.
- once it's out of retries, `nack(requeue=False)`, which dead-letters it to a
  DLX → DLQ where it sits so I can go look at it. no loop, nothing lost.

Sort of a fun detail: dead-lettering is used two different ways here. the retry
queue dead-letters on TTL expiry (that's the delay), and the main queue
dead-letters on rejection (that's giving up).

### Publisher confirms

The producer waits for the broker to confirm each publish (with a timeout), so
a publish that the broker never actually took gets logged instead of silently
disappearing. Each page is published in its own try/except so one bad page
doesn't kill the whole poll.

### Manual ack/nack

The consumer uses plain try/except with manual ack/nack instead of the
context-manager shortcut, because the retry-vs-give-up routing needs to control
where a failed message goes.

### Graceful shutdown

The consumer catches SIGINT and SIGTERM (SIGTERM is what Docker/k8s send to stop
a container) and closes its connection cleanly. in-flight messages are fine
because of ack-after-success + redelivery + idempotency — an abrupt stop can't
lose or duplicate anything. there's a fallback for Windows since asyncio's
signal handling doesn't work there.

### Auth from scratch

Argon2 hashing (pwdlib), JWTs (PyJWT), OAuth2 password flow — done by hand
instead of pulling in a library, since I wanted to actually understand how token
auth fits together.

### Scaling

Scaling the consumer is just running more copies. they all read from the same
queue and RabbitMQ spreads the messages across them (competing consumers);
`prefetch_count` controls how evenly it spreads. I tested this by running a few
consumers at once and watching the messages split up between them.

## Load testing

Load tested the three public GET endpoints with Locust. For the two endpoints
that take a coin, the coin can be anything — I just used bitcoin for testing.

(Rate limiting is toggled off for this via `APP_RATE_LIMIT_ENABLED=false`, so
the test measures real throughput instead of just hitting 429s.)

The scenarios I picked, ramping the load up each time:

- 20 users, 5/s ramp
- 50 users, 20/s ramp
- 200 users, 50/s ramp
- 500 users, 100/s ramp

| Scenario          | Setup                 | RPS | Median | Failures |
|-------------------|-----------------------|-----|--------|----------|
| 20 users, 5/s     | 1 worker              | 10  | 13ms   | 0%       |
| 50 users, 20/s    | 1 worker              | 25  | 13ms   | 0%       |
| 200 users, 50/s   | 1 worker, pool 20     | 99  | 20ms   | 0.3%     |
| 200 users, 50/s   | 1 worker, pool 100    | 99  | 9ms    | 0%       |
| 500 users, 100/s  | 1 worker, pool 100    | 49  | 4100ms | 95%      |
| 500 users, 100/s  | 4 workers, pool 100   | 250 | 10ms   | 0%       |

20 and 50 users were fine. The first issue showed up at the 200-user case — a
`MaxConnectionsError`. The Redis connection pool was set to the default of 20.
The way I understand it: a lot of requests come in, everyone wants a Redis
connection, but they're all occupied, so requests queue up somewhere and some
of them get dropped. Changing the pool to 100 fixed it — same load, 0 failures
(and the median actually dropped from 20ms to 9ms since requests weren't
waiting on a connection anymore).

Then I went to 500 users + 100/s on 1 worker, and hit a different issue. This
time the terminal showed no more MaxConnectionsError, so I suspected the single
worker just couldn't handle that many requests — they were piling up and timing
out (everything stuck at ~4100ms, 95% failures, and the RPS actually dropped
from 99 to 49). Bumping it to 4 workers (`uvicorn main:app --workers 4`) solved
it — same 500-user load, but 0 failures, 10ms median, ~250 RPS.

One thing on the slow tail: there's a ~2s spike on the first requests of each
run, then it settles to single-digit ms. That's cold start — the connection
pools warming up and the cache filling on first hit — not a recurring problem.

The Locust output for each run is in [`docs/`](docs/):

- [20 users](docs/load-test-20-users.png)
- [50 users](docs/load-test-50-users.png)
- [200 users — pool 20 (the failures)](docs/load-test-200-users-pool20.png)
- [200 users — pool 100 (fixed)](docs/load-test-200-users-pool100.png)
- [500 users — 1 worker (collapse)](docs/load-test-500-users-1worker.png)
- [500 users — 4 workers (fixed)](docs/load-test-500-users-4workers.png)

### What I took from it

Two bottlenecks, and they showed up in order. First the Redis connection pool:
the default of 20 ran out once a couple hundred users were hitting the cache at
once, and that was the first thing to start failing. Bumping it to 100 fixed
that. Second, the number of workers: even with Redis sorted out, a single worker
couldn't handle 500 concurrent requests, so I ran 4. What I found interesting is
that I only saw the worker problem clearly after fixing Redis — the bottlenecks
were stacked, and you fix them one at a time. The way they failed was a hint
too: the Redis one logged an actual error, but the worker one was silent (the
requests were timing out before they even reached the app). And none of it was
the app code — the same code did 250 RPS at 10ms once it was configured right.
How you run it (pool size, worker count) mattered as much as how it's written.

### Running it

```bash
# install locust (already in requirements.txt)
pip install locust

# run the app the production way (multiple workers)
uvicorn main:app --workers 4

# in another terminal, start locust
locust -f locustfile.py
# open http://localhost:8089, set users + host (http://localhost:8000)
```

## Deployment
I deployed this project three different ways, mostly to understand 
what each layer actually does. It's not hosted live right now, but 
everything needed to reproduce the setup is in this repo — refer to 
`docker-compose.prod.yml` and `nginx/nginx.conf`.

### How it's set up in production
nginx sits in front as the only container with published ports (80 
and 443). It handles the TLS certificate and redirects http to https, 
then proxies requests to the FastAPI app over Docker's internal 
network. The app talks to Redis for caching and publishes price 
updates to RabbitMQ, where a separate consumer worker (same Docker 
image, different start command) picks them up and writes to MongoDB 
Atlas. Nothing except nginx is reachable from the internet.

### The journey
I started with Railway because it was the fastest way to get 
something live. That worked, until MongoDB refused to start: it 
needs 500MB of *free* disk space, and Railway's trial caps volumes 
at exactly 500MB, so after Mongo's own files there wasn't enough 
left. That pushed me to MongoDB Atlas, which turned out to be the 
better setup anyway since managed databases are how most production 
systems work.
Then I redid the whole thing on a raw EC2 instance to learn what 
Railway was doing behind the scenes: setting up security groups and 
SSH, installing Docker on the server, writing a production compose 
file, configuring nginx as a reverse proxy, and getting a Let's 
Encrypt certificate working. Another thing I learnt while deploying 
to AWS was that certbot's auto-renewal would silently fail because 
nginx holds port 80 (fixed with renewal hooks). I also found that 
EC2 changes your public IP on every stop/start (fixed with a DuckDNS 
update script that runs on boot). 

## CI/CD

Every push to `main` runs a GitHub Actions pipeline: test suite first,
then a Docker build check. Tests are fully mocked, so CI needs no real
credentials — `.env.example` stands in for config.

Deploys are manual by design (the EC2 instance runs on-demand to save
costs): hit "Run workflow" and the pipeline tests, builds, then SSHes
in to pull and rebuild — using a dedicated deploy key stored in GitHub
Secrets.

## Status

### Done

- REST API (coins + market-data history)
- MongoDB with a compound index on `(coingecko_id, recorded_at)`, a TTL index to
  expire old data, and unique indexes where needed
- scheduled CoinGecko polling
- JWT auth (register / login / protected routes) from scratch
- Redis caching + rate limiting
- the RabbitMQ pipeline:
  - durable exchange + queue, persistent messages
  - retry queue with TTL delay + capped retries
  - DLX/DLQ for poison messages
  - publisher confirms with timeout
  - idempotent upsert with a publish-time timestamp
  - graceful shutdown (SIGINT/SIGTERM)
  - competing-consumers scaling
- tests across models, repositories, services, scheduler, API, auth, and the
  consumer's retry / dead-letter logic — all mocked, no live broker or DB needed
- dev setup works across Windows + macOS, synced through git
- load testing on the api endpoints with locust
- deployed three ways: Railway (PaaS), then MongoDB Atlas for the DB, then
  fully on AWS EC2 — Docker on a raw server, production compose file, nginx
  reverse proxy with TLS (Let's Encrypt + automated cert renewal), and DuckDNS
  with boot-time DNS updates

### Pending

- CI/CD — auto-deploy on push with GitHub Actions
- better logging around failed messages, consistent levels, maybe some metrics
- a couple more messaging tests (publish / publish-to-retry; the main consumer
  logic is already covered)

## Running it locally

Need Python 3.13+ and Docker.

Start the infra:

```bash
docker compose up -d
```

RabbitMQ dashboard: http://localhost:15672 (guest / guest).

Set up the env:

```bash
python -m venv .venv
source .venv/bin/activate          # mac/linux
# .venv\Scripts\Activate.ps1       # windows powershell
pip install -r requirements.txt
```

Config:

```bash
cp .env.example .env               # then fill it in
```

You need a CoinGecko API key and a JWT secret — they're listed in `.env.example`.

Run the API:

```bash
fastapi dev main.py
```

Docs at http://localhost:8000/docs.

Run the consumer (separate terminal):

```bash
python -m app.consumer
```

Run it in a few terminals at once if you want to see the consumers splitting work.

Tests:

```bash
pytest -v
```

## Notes

- `.env` is gitignored, `.env.example` has the list of what you need.
- again, the queue setup is heavier than the traffic calls for. it's there to
  exercise the patterns, not because gecko is drowning in data.
