#!/usr/bin/env python3
import json
from pathlib import Path
from dotenv import load_dotenv
from client import KISClient, load_config_from_env
import datetime as dt

Q=Path('/home/guidda/.openclaw/workspace/kis-openapi/.liquidation_queue.json')

def log(msg,obj=None):
    row={"ts":dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S KST'),"msg":msg}
    if obj is not None:
        row['payload']=obj
    print(json.dumps(row,ensure_ascii=False))


def main():
    if not Q.exists():
        log('queue_empty')
        return
    data=json.loads(Q.read_text(encoding='utf-8'))
    items=data.get('items',[])
    if not items:
        log('queue_empty_items')
        return

    load_dotenv('/home/guidda/.openclaw/workspace/kis-openapi/.env')
    cli=KISClient(load_config_from_env())

    remain=[]
    for it in items:
        s=str(it.get('symbol','')).strip()
        q=int(it.get('qty',0) or 0)
        if not s or q<=0:
            continue
        try:
            res=cli.order_cash_sell(symbol=s, qty=q, price=0, ord_dvsn='01')
            ok=str(res.get('rt_cd',''))=='0'
            log('sell_attempt',{'symbol':s,'qty':q,'result':res})
            if not ok:
                remain.append(it)
        except Exception as e:
            log('sell_error',{'symbol':s,'qty':q,'error':str(e)})
            remain.append(it)

    if remain:
        data['items']=remain
        Q.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        log('queue_remaining',{'count':len(remain)})
    else:
        Q.unlink(missing_ok=True)
        log('queue_done')

if __name__=='__main__':
    main()
