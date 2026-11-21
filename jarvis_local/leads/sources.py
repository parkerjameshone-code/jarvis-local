"""Where leads come from. Public data only, polite rate limit."""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from .store import Lead

USER_AGENT = "jarvis-local/0.1 (lead research; polite, low volume)"
MIN_GAP_S = 2.0
_last_call = [0.0]


def _get_json(url: str, sleep=time.sleep, now=time.monotonic) -> dict:
    wait = MIN_GAP_S - (now() - _last_call[0])
    if wait > 0:
        sleep(wait)
    _last_call[0] = now()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def parse_reddit(data: dict) -> list[Lead]:
    out = []
    for child in (data.get("data") or {}).get("children", []):
        d = child.get("data") or {}
        link = d.get("permalink")
        if not link:
            continue
        text = " ".join(x for x in (d.get("title"), d.get("selftext")) if x).strip()
        out.append(Lead("reddit", "https://www.reddit.com" + link, d.get("author") or "",
                        text, float(d.get("created_utc") or time.time())))
    return out


def reddit_search(query: str, limit: int = 25, fetch=_get_json) -> list[Lead]:
    url = ("https://www.reddit.com/search.json?sort=new&limit=%d&q=%s"
           % (max(1, min(limit, 100)), urllib.parse.quote(query)))
    return parse_reddit(fetch(url))


def parse_youtube_comments(data: dict) -> list[Lead]:
    out = []
    for item in data.get("items", []):
        top = (item.get("snippet") or {}).get("topLevelComment") or {}
        sn = top.get("snippet") or {}
        vid, cid = sn.get("videoId"), top.get("id")
        if not (vid and cid):
            continue
        out.append(Lead("youtube", f"https://www.youtube.com/watch?v={vid}&lc={cid}",
                        sn.get("authorDisplayName") or "", sn.get("textOriginal") or "", time.time()))
    return out


def youtube_comments(query: str, api_key: str, limit: int = 25, fetch=_get_json) -> list[Lead]:
    q = urllib.parse.urlencode({"part": "snippet", "searchTerms": query, "maxResults": min(limit, 100),
                                "order": "time", "key": api_key})
    return parse_youtube_comments(fetch("https://www.googleapis.com/youtube/v3/commentThreads?" + q))


class BrowserSearch:
    """Interface only. The host app's visible browser implements search()."""

    def search(self, query: str, limit: int = 25) -> list[Lead]:
        raise NotImplementedError("Plug in a browser that returns Lead objects.")
