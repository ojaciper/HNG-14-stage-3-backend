import re


class NaturalLanguageParser:
    def __init__(self):
        self.filters = {}

    def parse(self, query: str) -> dict:
        """Parse natural language query into filters"""
        query_lower = query.lower().strip()
        filters = {}

        # Age mappings for common terms
        age_mappings = {
            "baby": (0, 2),
            "toddler": (1, 3),
            "child": (4, 12),
            "preteen": (10, 12),
            "teen": (13, 19),
            "teenager": (13, 19),
            "young adult": (20, 30),
            "adult": (20, 59),
            "middle aged": (40, 60),
            "senior": (60, 120),
            "elderly": (65, 120),
        }

        # Gender detection
        male_keywords = [
            "male",
            "man",
            "boy",
            "gentleman",
            "guy",
            "men",
            "boys",
            "males",
        ]
        female_keywords = [
            "female",
            "woman",
            "girl",
            "lady",
            "women",
            "girls",
            "females",
        ]

        for keyword in male_keywords:
            if keyword in query_lower:
                filters["gender"] = "male"
                break
        for keyword in female_keywords:
            if keyword in query_lower:
                filters["gender"] = "female"
                break

        # Age group detection
        age_groups = ["child", "teenager", "adult", "senior"]
        for group in age_groups:
            if group in query_lower:
                filters["age_group"] = group

        # Special "young" mapping (16-24)
        if "young" in query_lower:
            filters["min_age"] = 16
            filters["max_age"] = 24

        # Age ranges from keywords
        for keyword, (min_age, max_age) in age_mappings.items():
            if keyword in query_lower:
                if "min_age" not in filters:
                    filters["min_age"] = min_age
                if "max_age" not in filters:
                    filters["max_age"] = max_age

        # Age with numbers (above, over, >)
        age_pattern_above = r"(?:above|over|older than|>=?|>)\s*(\d+)"
        matches = re.findall(age_pattern_above, query_lower)
        if matches:
            filters["min_age"] = int(matches[0])

        # Age with numbers (below, under, <)
        age_pattern_below = r"(?:below|under|younger than|<=?|<)\s*(\d+)"
        matches = re.findall(age_pattern_below, query_lower)
        if matches:
            filters["max_age"] = int(matches[0])

        # Age range (between X and Y)
        age_pattern_range = r"between\s+(\d+)\s+and\s+(\d+)"
        matches = re.findall(age_pattern_range, query_lower)
        if matches:
            filters["min_age"] = int(matches[0][0])
            filters["max_age"] = int(matches[0][1])

        # Country detection
        country_mapping = {
            "nigeria": "NG",
            "kenya": "KE",
            "south africa": "ZA",
            "ghana": "GH",
            "uganda": "UG",
            "tanzania": "TZ",
            "angola": "AO",
            "senegal": "SN",
            "congo": "CD",
            "cameroon": "CM",
            "mali": "ML",
            "zambia": "ZM",
            "zimbabwe": "ZW",
            "rwanda": "RW",
            "sudan": "SD",
            "ethiopia": "ET",
            "morocco": "MA",
            "egypt": "EG",
            "tunisia": "TN",
            "algeria": "DZ",
            "us": "US",
            "usa": "US",
            "united states": "US",
            "uk": "GB",
            "united kingdom": "GB",
            "canada": "CA",
            "australia": "AU",
        }

        for country_name, country_code in country_mapping.items():
            if country_name in query_lower or f"from {country_name}" in query_lower:
                filters["country_id"] = country_code
                break

        return filters
