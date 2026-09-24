from __future__ import annotations

from typing import Any


# Stable sector identifiers are shared by public-opinion extraction and the
# event-thesis module. Keywords are evidence tags, not trading instructions.
SECTOR_TAXONOMY: dict[str, dict[str, Any]] = {
    "ai_compute": {
        "display_name": "AI computing",
        "keywords": ["人工智能", "AI", "大模型", "算力", "数据中心", "光模块", "CPO", "机器人"],
    },
    "semiconductors": {
        "display_name": "Semiconductors",
        "keywords": [
            "半导体",
            "芯片",
            "存储",
            "晶圆",
            "先进制程",
            "光刻",
            "封装测试",
            "SOX",
            "Philadelphia Semiconductor Index",
        ],
    },
    "oil_gas": {
        "display_name": "Oil and gas",
        "keywords": [
            "石油",
            "原油",
            "天然气",
            "油气",
            "布伦特",
            "WTI",
            "Brent",
            "OPEC",
            "霍尔木兹",
        ],
    },
    "gold": {
        "display_name": "Gold",
        "keywords": ["黄金", "金价", "贵金属", "Gold", "XAU", "COMEX黄金"],
    },
    "crypto": {
        "display_name": "Crypto assets",
        "keywords": ["比特币", "加密资产", "数字货币", "Bitcoin", "BTC", "Ethereum", "ETH"],
    },
    "rates_fx": {
        "display_name": "Rates and foreign exchange",
        "keywords": [
            "利率",
            "降息",
            "加息",
            "汇率",
            "美元指数",
            "人民币汇率",
            "美债收益率",
            "DXY",
            "US10Y",
            "CNH",
        ],
    },
    "shipping": {
        "display_name": "Shipping",
        "keywords": [
            "航运",
            "集运",
            "油运",
            "干散货",
            "运价",
            "港口",
            "红海",
            "波罗的海干散货指数",
            "BDI",
        ],
    },
    "digital_economy": {
        "display_name": "Digital economy",
        "keywords": ["数字经济", "数据要素", "信创", "网络安全", "鸿蒙", "云计算", "工业互联网"],
    },
    "brokerage_finance": {
        "display_name": "Brokerage and capital market",
        "keywords": [
            "券商",
            "证券",
            "资本市场",
            "交易所",
            "融资融券",
            "并购重组",
            "注册制",
            "印花税",
        ],
    },
    "state_owned_reform": {
        "display_name": "SOE reform",
        "keywords": ["国企改革", "央企", "市值管理", "资产注入", "混改", "重组"],
    },
    "new_energy": {
        "display_name": "New energy",
        "keywords": ["新能源", "光伏", "储能", "锂电", "电池", "风电", "充电桩", "固态电池"],
    },
    "low_altitude": {
        "display_name": "Low-altitude economy",
        "keywords": ["低空经济", "无人机", "通航", "eVTOL", "飞行汽车", "空管"],
    },
    "medicine": {
        "display_name": "Medicine",
        "keywords": ["创新药", "医药", "医疗器械", "CRO", "疫苗", "中药"],
    },
    "consumer": {
        "display_name": "Consumer",
        "keywords": ["消费", "食品饮料", "白酒", "旅游", "免税", "家电", "汽车"],
    },
    "infrastructure": {
        "display_name": "Infrastructure",
        "keywords": ["基建", "水利", "特高压", "电网", "铁路", "工程机械", "城市更新"],
    },
    "defense": {
        "display_name": "Defense",
        "keywords": ["军工", "航空发动机", "卫星", "北斗", "航天", "雷达"],
    },
}


INDUSTRY_CHAIN_EDGES: dict[str, tuple[dict[str, str], ...]] = {
    "semiconductors": (
        {
            "from": "global_ai_hardware",
            "to": "chip_design",
            "relation": "demand_spillover",
            "direction": "positive",
        },
        {
            "from": "chip_design",
            "to": "foundry_and_equipment",
            "relation": "capacity_demand",
            "direction": "positive",
        },
    ),
    "oil_gas": (
        {
            "from": "global_crude_supply",
            "to": "crude_price",
            "relation": "supply_balance",
            "direction": "inverse",
        },
        {
            "from": "crude_price",
            "to": "upstream_producers",
            "relation": "price_realization",
            "direction": "positive",
        },
    ),
    "gold": (
        {
            "from": "real_rates_and_risk_aversion",
            "to": "gold_price",
            "relation": "opportunity_cost_and_safe_haven",
            "direction": "mixed",
        },
    ),
    "crypto": (
        {
            "from": "global_liquidity",
            "to": "crypto_assets",
            "relation": "risk_liquidity",
            "direction": "positive",
        },
    ),
    "rates_fx": (
        {
            "from": "policy_rate_expectations",
            "to": "currency_and_bond_yields",
            "relation": "discount_rate",
            "direction": "mixed",
        },
    ),
    "shipping": (
        {
            "from": "route_disruption",
            "to": "freight_rates",
            "relation": "effective_capacity",
            "direction": "positive",
        },
    ),
}
