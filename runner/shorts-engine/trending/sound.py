import json,sys,urllib.request,re
def reel_body(vid):
    return {"context":{"client":{"clientName":"WEB","clientVersion":"2.20261030.02.00","hl":"en","gl":"GB"}},
          "playerRequest":{"videoId":vid},"params":"CAUwAg%3D%3D","disablePlayerResponse":True}
def reel(vid):
    body=reel_body(vid)
    r=urllib.request.Request("https://www.youtube.com/youtubei/v1/reel/reel_item_watch?prettyPrint=false",data=json.dumps(body).encode(),headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0"})
    return json.load(urllib.request.urlopen(r,timeout=30))
def find(o,key):
    if isinstance(o,dict):
        if key in o: yield o[key]
        for v in o.values(): yield from find(v,key)
    elif isinstance(o,list):
        for v in o: yield from find(v,key)
def sound(vid): return sound_from(reel(vid))
def sound_from(d):
    t=next((p.get('soundAttributionTitle',{}).get('content') for p in find(d,'pivotButtonViewModel') if 'soundAttributionTitle' in p),None)
    if not t: return None
    h=next(find(d,'pageHeaderViewModel'),{})
    src=next(find(h,'watchEndpoint'),{}).get('videoId')
    parts=[x.get('text',{}).get('content') for x in find(h,'metadataParts')for x in x]
    return {'title':t,'source':src,'meta':[p for p in parts if p]}
if __name__=='__main__':
    for v in sys.argv[1:]: print(v, sound(v))
