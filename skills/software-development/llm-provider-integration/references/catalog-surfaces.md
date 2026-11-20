# Model counts across a gateway's surfaces

A gateway exposes several different model counts. They are legitimately unequal; treating the difference as a bug wastes a session. Identify the surface first.

## The three surfaces

| Surface | Backing store | One entry per | Typical admin label |
|---|---|---|---|
| Routing / routes table | `model_routes` (or equivalent) | client-facing alias the operator created | "Routing", "Route Model" |
| Discovered / imported catalog | per-channel imported models, fetched from upstream `GET {base}/models` | model the provider returned | "Models", "Import All Discovered Models" |
| Published catalog | derived from `model_routes` at request time by `GET /v1/models` | every id the gateway is willing to accept | (no admin page; client-facing) |

A model picker or "available models" dropdown inside the admin dashboard usually reads the **published** or **discovered** list, while the table next to it reads the **routing table**. A picker showing 12 entries beside a route count of 3 is working as designed.

Metadata follows its surface: tier/quality badges on a model row (`tierTag`, `badge`, a `MED`-style pill) are classified from the **upstream** model entry during discovery, not stored on the route. Editing a route does not change them.

## Diagnosing a count mismatch

1. Ask (or determine) which endpoint or table the reporting screen reads. Grep for the component's data source before theorising about the router.
2. Fetch `GET /v1/models` with the operator's own key (read-only `scripts/probe_provider.sh` pattern; never echo the key), save the JSON, then group it locally by display name so the route/id relationship is explicit:

```python
import json, collections
d = json.load(open("models.json"))["data"]
print("entries", len(d))
for name, group in collections.groupby(
    sorted(d, key=lambda m: m.get("display_name") or m["id"]),
    key=lambda m: m.get("display_name") or m["id"],
):
    print(len(list(group)), name, [m["id"] for m in list(group)])
```

Key the grouping with `display_name or id` — a route whose display name is empty publishes only its slug and would otherwise vanish into a `None` bucket. Distinct display-name count = route count; each group is one route's id expansion. The field name also proves which emission path produced the entries.

3. Only if the grouping does not match the expected route count is there a real defect (duplicate routes, orphan rows, an emission path that produces an id no route owns).

## Removing the duplication

Do not drop the hyphen/dot aliases to shorten the list. They exist so client SDKs that ship a normalized model catalog resolve the route under the vendor's own convention. If the operator genuinely wants one id per route, gate the aliases behind a per-route flag rather than deleting the emission branch.
