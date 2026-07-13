
This is the aspirational API:

```python
import tangler  # or whatever it ends up being called
from tangler import EntityPool, EntityType, Source, Key, Feature
from tangler.constraints import Coverage, Overlap, Duplicates
from tangler.rules import SuffixRule, ReplaceRule

# Declare the pool
pool = EntityPool(seed=42)
pool.add(EntityType("company", n=100))

# Declare features
company_name = Feature("company_name", generator="company")
crn = Feature("crn", generator="bothify", params={"text": "???-###-???-###"})
address = Feature("address", generator="address")

# Declare sources
companies_house = Source("companies_house", key=Key("ch_id", generator="numerify"))
companies_house.add(company_name, perturbations=[SuffixRule(" Ltd"), SuffixRule(" Limited")])
companies_house.add(crn)
companies_house.add(address)

crm = Source("crm", key=Key("crm_ref", generator="uuid4"))
crm.add(company_name, perturbations=[ReplaceRule("&", "and")])
crm.add(address)

# Declare constraints
pool.constrain(
    Coverage(companies_house, ratio=1.0),   # all entities appear in CH
    Coverage(crm, ratio=0.6),               # 60% appear in CRM
    Overlap(companies_house, crm, ratio=0.6),
    Duplicates(crm, rate=0.1),
)

# Generate
bundle = tangler.generate(pool, companies_house, crm)

# Raw data
bundle.data.datasets["companies_house"]  # pl.DataFrame
bundle.data.datasets["crm"]             # pl.DataFrame
bundle.data.nodes                        # (entity_id, entity_type)
bundle.data.edges                        # (entity_id, source, key)

# Correctness
true_clusters = bundle.correctness.clusters(companies_house, crm)

predicted: pl.DataFrame  # (cluster_id, entity_type, source, key) — user's algorithm output
diff = bundle.correctness.diff(predicted, sources=[companies_house, crm])

diff.perfect   # got these exactly right
diff.splits    # fragmented these
diff.merges    # collapsed these
diff.missed    # didn't touch these

# Drill into perturbation failures
bundle.correctness.splits_caused_by(SuffixRule)
bundle.correctness.provenance("ch_001", source=companies_house)
# returns {"company_name": [SuffixRule(" Ltd")]}
```