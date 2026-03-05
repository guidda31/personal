SECTOR_THEME_DB = {
    "by_symbol": {
        "004090": "oil",
        "014530": "oil",
        "117580": "gas",
        "024060": "oil",
        "003280": "shipping",
        "152550": "oil",
        "053050": "gas",
        "272210": "defense",
        "012450": "defense",
        "047810": "aerospace",
        "005930": "semicon",
        "000660": "semicon",
        "001510": "finance"
    },
    "name_rules": [
        {"contains": ["정유", "석유", "oil"], "theme": "oil"},
        {"contains": ["가스", "lng", "lpg", "도시가스"], "theme": "gas"},
        {"contains": ["에너지", "전력", "파워", "energy"], "theme": "energy"},
        {"contains": ["해운", "shipping", "marine", "물류"], "theme": "shipping"},
        {"contains": ["조선", "ship", "중공업"], "theme": "shipbuilding"},
        {"contains": ["방산", "defense", "디펜"], "theme": "defense"},
        {"contains": ["항공우주", "우주", "aero", "space"], "theme": "aerospace"},
        {"contains": ["반도체", "semicon", "전자", "테크"], "theme": "semicon"},
        {"contains": ["바이오", "제약", "bio", "pharma"], "theme": "bio"},
        {"contains": ["증권", "은행", "금융", "보험", "캐피탈"], "theme": "finance"}
    ]
}
