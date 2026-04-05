import time, json, urllib.request, os, sys
from datetime import datetime

def fetch(path):
    try:
        r = urllib.request.urlopen(f'http://localhost:3001{path}', timeout=3)
        return json.loads(r.read())
    except:
        return None

log = []
start_time = datetime.now()
start_arb = None
start_trades = None

print('POLY_TEX OPPORTUNITY MONITOR')
print('Watching for: arb profit, resolved trades, real edges')
print('─'*60)

while True:
    try:
        s = fetch('/api/state')
        now = datetime.now().strftime('%H:%M:%S')

        if s:
            arb_p   = float(s.get('arbProfit', 0) or 0)
            pnl     = float(s.get('totalPnL', 0) or 0)
            trades  = int(s.get('tradesExecuted', 0) or 0)
            dip_t   = int(s.get('dipArbTrades', 0) or 0)
            capital = float(s.get('currentCapital', 1000) or 1000)
            redeems = int(s.get('redeems', 0) or 0)

            if start_arb is None:
                start_arb = arb_p
                start_trades = trades

            # Log any change
            entry = f'[{now}] ARB:${arb_p:.4f} PNL:${pnl:.4f} TRADES:{trades} DIPARB:{dip_t} REDEEMS:{redeems} CAPITAL:${capital:.2f}'

            if log and log[-1] != entry:
                print(entry)
                log.append(entry)

                # Highlight meaningful events
                if arb_p > start_arb:
                    print(f'  ✅ ARB PROFIT INCREASED: +${arb_p - start_arb:.4f}')
                if pnl > 0:
                    print(f'  ✅ POSITIVE PNL: ${pnl:.4f}')
                if redeems > 0:
                    print(f'  ✅ POSITION REDEEMED: {redeems} times')
            elif not log:
                print(entry)
                log.append(entry)

        runtime = datetime.now() - start_time
        hrs = int(runtime.total_seconds() // 3600)
        mins = int((runtime.total_seconds() % 3600) // 60)

        # Summary every 5 mins
        if len(log) % 300 == 0 and log:
            print(f'\n  ── {hrs}h {mins}m elapsed ──')
            print(f'  Arb profit so far : ${(s or {}).get("arbProfit",0):.4f}')
            print(f'  Total PnL         : ${(s or {}).get("totalPnL",0):.4f}')
            print(f'  Verdict so far    : {"🟢 showing profit" if float((s or {}).get("totalPnL",0) or 0) > 0 else "🟡 break even" if float((s or {}).get("totalPnL",0) or 0) == 0 else "🔴 loss"}')
            print()

        time.sleep(1)

    except KeyboardInterrupt:
        print('\n─'*60)
        print('FINAL SUMMARY')
        if s:
            arb_p  = float(s.get('arbProfit', 0) or 0)
            pnl    = float(s.get('totalPnL', 0) or 0)
            cap    = float(s.get('currentCapital', 1000) or 1000)
            print(f'  Arb profit  : ${arb_p:.4f}')
            print(f'  Total PnL   : ${pnl:.4f}')
            print(f'  Capital     : ${cap:.2f}')
            if arb_p > 0:
                print('  VERDICT: ✅ ARB WORKING — worth going live')
            elif pnl > 0:
                print('  VERDICT: ✅ PROFITABLE — consider going live')
            else:
                print('  VERDICT: 🟡 NO PROFIT YET — keep monitoring')
        sys.exit(0)
    except Exception as e:
        print(f'Error: {e}')
        time.sleep(1)
