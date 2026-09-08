# shared.web — specification only
No scraping code. Defines per status type (lift, hut, pass, road, fire ban, shooting schedule, natural hazard,
media) the query templates in four languages, preferred sources, the verification rule and the output shape
(`WebVerification`: verified | unverified | conflicting, url, ≤ 15-word quote, timestamps). The LLM performs the
search with its web tool and hands the result back; core stores it as Evidence class A (verified) or leaves
the status `unverified`. Absence of information never becomes open/closed (SR-3).
