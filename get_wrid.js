const crypto = require('crypto');

function zL(o) {
    if (o == null)
        throw new Error("Illegal argument " + o);
    return crypto.createHash('md5').update(o).digest('hex');
}

let wts = Math.round(Date.now() / 1000);
u= [
    "__refresh__=true",
    "_extra=",
    "ad_resource=5654",
    "category_id=",
    "context=",
    "dynamic_offset=0",
    "from_source=",
    "from_spmid=333.337",
    "gaia_vtoken=",
    "highlight=1",
    "keyword=%E8%B4%A2%E6%8A%A5%26%E6%98%9F%E9%99%85%E6%88%98%E7%94%B2",
    "page=1",
    "page_size=42",
    "platform=pc",
    "pubtime_begin_s=1773244800",
    "pubtime_end_s=1773935999",
    "qv_id=sEAYydeeGhZtBVQMhC5FbLK8W6D7hzsU",
    "search_type=video",
    "single_column=0",
    "source_tag=3",
    "web_location=1430654",
    "web_roll_page=1",
    "wts=" + wts
]
f = u.join("&")
p = zL(f + "ea1db124af3c7062474693fa704f4ff8")

console.log({ wts, p })