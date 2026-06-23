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

### Pending

- better logging around failed messages, consistent levels, maybe some metrics
- a couple more messaging tests (publish / publish-to-retry; the main consumer
  logic is already covered)
- load testing (Locust or k6) to find where it falls over and check the scaling
  actually holds
- deployment — containerize everything, get it on a cloud host, run the consumer
  as its own service, real secrets, CI/CD

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
