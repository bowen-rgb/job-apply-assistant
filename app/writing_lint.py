"""Explainable plain-writing checks ported from Apply-Pilot src/lint.mjs (MIT)."""
import re

STOCK_PHRASES=['passionate','dynamic','leverage','spearhead','cutting-edge','cutting edge','synergy','delve',
 'tapestry','testament to','i am writing to express','thrilled','excited to apply','unique opportunity',
 'perfect fit','ideal candidate','hit the ground running','fast-paced','results-driven','go-getter',
 'this experience taught me','taught me the importance','i firmly believe',"in today's",'deeply passionate',
 'strong passion','navigate the complexities','ever-evolving','pivotal role']


def lint(text,rules=None):
    if not isinstance(rules or {},dict):raise ValueError('Writing rules must be an object')
    for key in ('bannedPhrases','forbiddenClaims'):
        values=(rules or {}).get(key,[])
        if not isinstance(values,list) or len(values)>100 or any(not isinstance(v,str) or not 1<=len(v)<=200 for v in values):raise ValueError('Use at most 100 plain phrases per writing rule')
    rules=rules or {};issues=[];sentences=[s for s in re.split(r'(?<=[.!?])\s+',' '.join(text.split())) if s.strip()]
    for phrase in STOCK_PHRASES+rules.get('bannedPhrases',[]):
        if str(phrase).casefold() in text.casefold():issues.append({'rule':'stock-phrase','detail':phrase})
    for claim in rules.get('forbiddenClaims',[]):
        for sentence in sentences:
            if re.search(r'(?<!\w)'+re.escape(claim)+r'(?!\w)',sentence,re.I) and not re.search(r"\b(not|never|no|haven't|have not|hasn't|without|yet to|would learn|new to me|pas|jamais|sans)\b|没有|尚未|未掌握",sentence,re.I):
                issues.append({'rule':'forbidden-claim','detail':claim+': '+sentence[:120]})
    if text.count(';')>int(rules.get('maxSemicolons',0)):issues.append({'rule':'semicolons','detail':text.count(';')})
    if text.count('—')>1:issues.append({'rule':'em-dashes','detail':text.count('—')})
    for sentence in sentences:
        if sentence.count(',')>=4 and ' and ' in sentence:issues.append({'rule':'long-list','detail':sentence[:120]})
        if len(sentence.split())>40:issues.append({'rule':'long-sentence','detail':sentence[:120]})
    return {'issues':issues,'stats':{'words':len(text.split()),'sentences':len(sentences),
             'meanWords':round(sum(len(s.split()) for s in sentences)/max(1,len(sentences)),1)},
             'note':'Style checks only. Existing LM factual review remains mandatory.'}
