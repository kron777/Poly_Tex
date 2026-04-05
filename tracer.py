import time, json, urllib.request, os, sys
from datetime import datetime

def clear(): os.system('clear')

def fetch(path):
    try:
        r = urllib.request.urlopen(f'http://localhost:3001{path}', timeout=3)
        return json.loads(r.read())
    except:
        return None

prev_trades = 0

while True:
    try:
        clear()
        now = datetime.now().strftime('%H:%M:%S')
        s = fetch('/api/state')

        print('╔══════════════════════════════════════════════════════════╗')
        print(f'║  POLY_TEX LIVE TRACER  {now}  [1s refresh]          ║')
        print('╚══════════════════════════════════════════════════════════╝')

        if s:
            usdc    = float(s.get('usdcBalance', 0) or 0)
            usdce   = float(s.get('usdcEBalance', 0) or 0)
            matic   = float(s.get('maticBalance', 0) or 0)
            capital = float(s.get('currentCapital', 0) or 0)
            peak    = float(s.get('peakCapital', 0) or 0)
            pnl     = float(s.get('totalPnL', 0) or 0)
            dpnl    = float(s.get('dailyPnL', 0) or 0)
            mpnl    = float(s.get('monthlyPnL', 0) or 0)
            upnl    = float(s.get('unrealizedPnL', 0) or 0)
            trades  = int(s.get('tradesExecuted', 0) or 0)
            sm_t    = int(s.get('smartMoneyTrades', 0) or 0)
            arb_t   = int(s.get('arbTrades', 0) or 0)
            dip_t   = int(s.get('dipArbTrades', 0) or 0)
            arb_p   = float(s.get('arbProfit', 0) or 0)
            c_wins  = int(s.get('consecutiveWins', 0) or 0)
            c_loss  = int(s.get('consecutiveLosses', 0) or 0)
            draw    = float(s.get('currentDrawdown', 0) or 0)
            wallets = s.get('followedWallets', [])
            dip_mkt = s.get('activeDipArbMarket', 'None')
            arb_mkt = s.get('activeArbMarket', 'None')
            btc     = s.get('btcTrend', '?')
            eth     = s.get('ethTrend', '?')
            sol     = s.get('solTrend', '?')
            halted  = s.get('permanentlyHalted', False)
            paused  = s.get('isPaused', False)
            splits  = s.get('splits', 0)
            merges  = s.get('merges', 0)
            redeems = s.get('redeems', 0)

            new_t = ' 🔔 NEW!' if trades > prev_trades else ''
            prev_trades = trades
            pnl_c = '\033[92m' if pnl >= 0 else '\033[91m'
            rst = '\033[0m'
            status = '🔴 HALTED' if halted else '⏸ PAUSED' if paused else '▶ RUNNING'

            print()
            print(f'  {status}')
            print()
            print(f'  💰 WALLET                           📊 P&L')
            print(f'     USDC.e  : ${usdce:>10,.2f}          Total   : {pnl_c}{pnl:>+.4f}{rst}')
            print(f'     USDC    : ${usdc:>10,.2f}          Daily   : {dpnl:>+.4f}')
            print(f'     MATIC   : {matic:>11.4f}          Monthly : {mpnl:>+.4f}')
            print(f'     Capital : ${capital:>10,.2f}          Unreal  : {upnl:>+.4f}')
            print(f'     Peak    : ${peak:>10,.2f}          Drawdown: {draw:.2f}%')
            print()
            print(f'  📈 TRADES                           🤖 SMART MONEY')
            print(f'     Total   : {trades:<8}{new_t:<12}  Wallets : {len(wallets)}')
            print(f'     SmartMon: {sm_t:<20}  Copies  : {sm_t}')
            print(f'     Arb     : {arb_t:<20}  Arb P&L : ${arb_p:.2f}')
            print(f'     DipArb  : {dip_t:<20}  Con.Win : {c_wins}')
            print(f'     Direct  : {s.get("directTrades",0):<20}  Con.Loss: {c_loss}')
            print()
            print(f'  📡 ACTIVE MARKETS')
            print(f'     DipArb : {str(dip_mkt)[:55]}')
            print(f'     Arb    : {str(arb_mkt)[:55]}')
            print()
            print(f'  📉 MARKET TRENDS')
            print(f'     BTC:{btc:<10} ETH:{eth:<10} SOL:{sol}')
            print()
            print(f'  ⛓  ON-CHAIN OPS')
            print(f'     Splits:{splits}  Merges:{merges}  Redeems:{redeems}')
            print()
            print(f'  👛 TRACKED WALLETS')
            for w in wallets:
                print(f'     {w}')

            # Positions
            positions = s.get('positions', [])
            if positions:
                print()
                print(f'  📦 OPEN POSITIONS ({len(positions)})')
                for p in positions[:5]:
                    print(f'     {str(p)[:70]}')
        else:
            print('\n  ⚠️  Bot offline')

        print()
        print('  ⚡ 1s refresh — Ctrl+C to exit')
        time.sleep(1)

    except KeyboardInterrupt:
        print('\nTracer stopped.')
        sys.exit(0)
    except Exception as e:
        print(f'  Error: {e}')
        time.sleep(1)
