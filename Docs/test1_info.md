# Design choices for simplification
Pytest 

- Ignoring Glitch cards initially
- Assuming following structure for json files storing cards:
Action cards:

```
{
  "cards": [
    {
      "name": "Satellite Surveillance",
      "description": "Deploy satellite recon",
      "category": "Intelligence",
      "responsibility": 2,
      "effect": 3
    },
    {
      "name": "Zero-Day Exploit",
      "description": "Advanced system breach",
      "category": "Technology",
      "responsibility": 1,
      "effect": 4
    }
  ]
}
```

Objective Cards:
```
{
  "cards": [
    {
      "name": "Disrupt Supply Chain",
      "description": "Interrupt logistics network",
      "responsibility": 1,
      "effect": 2
    }
  ]
}
```


