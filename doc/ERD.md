Battery Capacity ERD
====================

```mermaid
---
title: Battery Capacity
---

erDiagram
    direction TB
    battery {
        id integer PK
        created timestamp
        modified timestamp
        bat_id varchar(20) UK
        mah integer
    }

    bat_soc_history {
        id integer PK
        created timestamp
        battery_id integer FK
        soc_uid text UK
        mah integer
        dch_accuracy integer
    }

    soc_event {
        id integer PK
        created timestamp
        bc_name text
        state text
        bat_id varchar(20)
        bat_v integer
        adc_v integer
        current integer
        charge integer
        mah integer
        period integer
        shunt real
        soc_state text
        soc_cycle smallint
        soc_cycles smallint
        soc_cycle_period integer
        soc_uid text
        soc_history_id integer FK
    }

    bat_soc_history ||--|{ soc_event: "has"
    battery ||--|{ bat_soc_history: "has"
```
