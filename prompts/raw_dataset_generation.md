Generate synthetic restaurant menus.

Requirements:

- Generate realistic raw menu data.
- Each restaurant should feel like one coherent menu from one merchant.
- Include typos, inconsistent casing, missing descriptions, abbreviations, vague item names, and inconsistent naming conventions.
- Include occasional ambiguous items such as `Chef's Special`, `House Bowl`, `Combo Plate`, or `Lunch Special`.
- Include occasional cross-cuisine items such as Korean tacos, tikka pizza, or sushi burritos.
- Leave natural gaps in each menu so later stages can suggest missing opportunities.
- Prices must be numeric JSON numbers, not strings.
- Descriptions may be empty strings.
- Avoid duplicate restaurant names.
- Avoid duplicate item names within a restaurant menu.
