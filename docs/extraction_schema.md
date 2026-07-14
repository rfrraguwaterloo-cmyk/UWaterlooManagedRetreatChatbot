# Extraction Schema

Fields captured from each managed retreat case study:

| Field | Description | Values |
|-------|-------------|--------|
| `case_id` | Unique identifier (CS1–CS8) | string |
| `location` | Place name | string |
| `country` | Canada / USA / Indonesia | string |
| `hazard_type` | Primary climate hazard | string |
| `trigger` | What initiated the retreat | string |
| `year_initiated` | Year retreat process began | integer |
| `stage` | Where the case is in the process | `pre-retreat`, `during`, `post-retreat` |
| `governance` | Governing body (municipal, federal, First Nation, etc.) | string |
| `funding_mechanism` | How the retreat was/is funded | string |
| `compensation_type` | What residents received | string |
| `voluntariness` | Degree of choice for residents | `voluntary`, `incentivized`, `involuntary` |
| `equity_outcomes` | Who benefited/was harmed | string |
| `implementation_barriers` | List of obstacles encountered | array |
| `community_engagement` | How the community was involved | string |
| `success_rating` | Researcher assessment | `successful`, `failed`, `ongoing` |
| `source` | Citation for the case study | string |
