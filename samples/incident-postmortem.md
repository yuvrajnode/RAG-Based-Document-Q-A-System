# Postmortem: dispatch API outage, 14 February 2026

Status: closed. Author: platform on-call. Reviewed by the SRE guild on 21 Feb.

## Summary

Between 06:12 and 07:48 UTC the dispatch API returned HTTP 503 for roughly 62%
of requests. Route planning was unavailable for 96 minutes. 1,240 consignments
were delayed by an average of 41 minutes. No data was lost.

## Impact

- 62% of dispatch API requests failed with 503.
- Depot tablets fell back to the offline manifest, which was 14 hours stale.
- Two customer escalations were raised; both were closed the same day.

## Timeline

06:12 - Deployment 2026.2.14-a rolls out to the dispatch cluster.
06:14 - Connection pool saturation alert fires on dispatch-db-primary.
06:19 - On-call acknowledges. Initial hypothesis is a traffic spike.
06:37 - Traffic is confirmed normal. Hypothesis moves to the new deployment.
07:02 - Read replicas show near-zero load, ruling out overall query volume.
07:20 - The N+1 query in the route optimiser is identified as the cause.
07:31 - Rollback to 2026.2.11-c begins.
07:48 - Error rate returns to baseline. Incident downgraded.
09:00 - Consignment backlog cleared.

## Root cause

Deployment 2026.2.14-a changed the route optimiser to load stop details lazily.
Each route plan then issued one query per stop instead of a single batched
query. At a median of 34 stops per route, database connections per request rose
from 1 to 35, and the pool of 200 connections was exhausted within two minutes
of the rollout.

The change passed review and staging because the staging dataset averages three
stops per route, so the query amplification was 3x rather than 34x and stayed
inside the pool.

## What went well

Alerting fired within two minutes. The rollback path worked exactly as designed
and completed in 17 minutes.

## What did not

Diagnosis took 66 minutes of the 96 minute outage. Connection-pool utilisation
was not on the primary dashboard, so the first 25 minutes were spent on the
wrong hypothesis. Staging data was not representative of production shape.

## Actions

- PLAT-2291: add connection pool utilisation to the primary dashboard. Done.
- PLAT-2292: seed staging with a production-shaped route distribution. Due 31 March.
- PLAT-2293: add a query-count assertion to the route optimiser test suite. Due 14 March.
- PLAT-2294: canary the dispatch cluster at 5% for 15 minutes before full rollout. Due 30 April.
