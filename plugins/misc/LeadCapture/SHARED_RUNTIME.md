# Shared runtime

LeadCapture declares `shared-runtime-v1` and `stateless-v1`. The EventListener keeps no invocation data; it reads configuration and the installation binding only inside event invocations.

State rows are keyed by `instance_uuid:workspace_uuid:installation_uuid`, bot UUID and user ID, one row per customer (`asked` or `captured`, plus email delivery status). A shared worker without a binding refuses storage access; dedicated placement uses a dedicated scope. One process-local lock per installation serializes judging, contact capture and email delivery so a customer is asked at most once. Revocation removes only the affected lock. No background tasks are created: judging runs inside `NormalMessageResponded`, capture and email inside `PersonMessageReceived`, and failed emails are retried only on later events of the same customer.
