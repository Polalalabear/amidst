"""Conservative literal-only Q3 grammar. No clock, model, media or answer data."""
from dataclasses import dataclass
import hashlib
import json
import re
from pathlib import Path

VERSION='q3-rules.v1'
SOURCE_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
_NUM=r'[0-9零〇一二兩三四五六七八九十]+'
_SIMPLE=rf'(?:上午|下午)?\s*(?:{_NUM}[點点時时](?:半|{_NUM}分?)?(?:{_NUM}秒)?|\d{{1,2}}:\d{{2}}(?::\d{{2}}(?:\.\d{{1,6}})?)?)'
_ISO=r'\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})'
TIME_PATTERN=re.compile(_ISO+'|'+_SIMPLE)
DATE_PATTERN=re.compile(r'\d{4}-\d{2}-\d{2}')
GRAMMAR=('請問','可以','幫我','找出','查詢','哪幾台相機','哪台相機','哪些鏡頭','哪幾台','哪一台','哪台','哪些','拍到','的人','穿著','穿','衣服','衣','經過哪裡','在哪裡','在哪','之間','開始','結束','到','從','裡面','畫面','鏡頭','相機','有','在','的','和','與','及','找','看','查','嗎','？','?','。','，',',','：',':','、','～','~','–','—','-','至',' ','\t','\n')
UNSUPPORTED_PATTERN=re.compile(r'戴眼鏡|戴帽|真實姓名|身份|身分|actor_id|ground_truth|人物設定|事件腳本|GT|/Users/|/private/|/tmp/')
SPEC_SHA256=hashlib.sha256(json.dumps({'version':VERSION,'time':TIME_PATTERN.pattern,'date':DATE_PATTERN.pattern,'grammar':GRAMMAR,'unsupported':UNSUPPORTED_PATTERN.pattern},sort_keys=True,separators=(',',':')).encode()).hexdigest()


@dataclass(frozen=True)
class RuleResult:
    output: dict
    unparsed: tuple[str,...]
    unsupported_condition: bool


def _terms(text,aliases):
    found=[]
    for term,label in sorted(aliases.items(),key=lambda p:(-len(p[0]),p[0])):
        pattern=re.escape(term)
        if term.isascii():pattern=r'(?<![A-Za-z])'+pattern+r'(?![A-Za-z])'
        for match in re.finditer(pattern,text,re.IGNORECASE):found.append((match.start(),match.end(),match.group(),label))
    # Nested aliases for the same label are one literal, never two conditions.
    chosen=[]
    for item in sorted(found,key=lambda m:(-(m[1]-m[0]),m[0],m[2])):
        if not any(item[0]>=x[0] and item[1]<=x[1] and item[3]==x[3] for x in chosen):chosen.append(item)
    return sorted(chosen)


def parse_rule(text,*,class_aliases,color_aliases,camera_aliases,region_aliases):
    if not isinstance(text,str) or not text.strip():raise ValueError('Nonempty text required')
    groups=[_terms(text,a) for a in (class_aliases,color_aliases,camera_aliases,region_aliases)]
    classes,colors,cameras,regions=groups;times=list(TIME_PATTERN.finditer(text));dates=list(DATE_PATTERN.finditer(text))
    mask=[False]*len(text)
    for group in groups:
        for start,end,_,_ in group:mask[start:end]=[True]*(end-start)
    for match in times+dates:mask[match.start():match.end()]=[True]*(match.end()-match.start())
    rest=''.join(' ' if marked else char for char,marked in zip(text,mask))
    for phrase in sorted(GRAMMAR,key=len,reverse=True):rest=rest.replace(phrase,' ')
    unparsed=tuple(x for x in re.split(r'\s+',rest) if x)
    def first(group):return max(group,key=lambda x:len(x[2]))[2] if group else None
    class_term=first(classes)
    # A lone unknown class token is surfaced to the closed table, not translated.
    if not class_term and len(unparsed)==1 and not any(v in text for v in ['找他','找她','那個人','剛剛那個']):class_term=unparsed[0]
    labels={x[3] for x in classes};intent='FIND_PERSON' if labels=={'person'} and not any(w in text for w in ['相機','鏡頭','哪幾台','哪些台']) else 'FIND_CAMERAS'
    if text.strip().startswith(('解釋','說明')):intent='EXPLAIN'
    unsupported=bool(UNSUPPORTED_PATTERN.search(text))
    ambiguous=(len(labels)>1 or len({x[3] for x in colors})>1 or len(times)!=2
               or len({m.group() for m in dates})>1 or class_term is None)
    output={'schema_version':'q-demo.q3-llm-output.v1','intent':intent,'class_term':class_term,'color_term':first(colors),
            'time_literal':{'start':times[0].group() if len(times)>=1 else None,'end':times[1].group() if len(times)>=2 else None,'date':dates[0].group() if dates else None},
            'camera_terms':list(dict.fromkeys(x[2] for x in cameras)),'region_terms':list(dict.fromkeys(x[2] for x in regions)),
            'needs_clarification':ambiguous,'clarification_question':'請補充明確的條件、起訖時間與範圍。' if ambiguous else None}
    return RuleResult(output,unparsed,unsupported)
