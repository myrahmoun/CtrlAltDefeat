# Design choices for simplification

- Ignoring Glitch cards initially
- Always draw up to 4 action cards to replace played ones (up to 6 in hand) after played turn. Later must change the design to give the player the chance to choose how many cards to draw.
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


