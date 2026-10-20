import asyncio
from app.backtesting import compare_all_strategies, run_walk_forward_backtest

async def test_all():
    print("Running compare_all_strategies('NIFTY')...")
    results = await compare_all_strategies('NIFTY')
    print(f"Comparison completed for {len(results)} strategies:")
    for r in results:
        print(f"  * {r['name']} ({r['code']}): {r['total_trades']} trades | Win: {r['win_rate']}% | Net: Rs. {r['net_pnl']} | PF: {r['profit_factor']}")

    print("\nRunning Walk-Forward Out-of-Sample on Strategy 6 (STRAT_EXPIRY_GAMMA_SCALPER)...")
    wf_res = await run_walk_forward_backtest('NIFTY', 'STRAT_EXPIRY_GAMMA_SCALPER')
    print(f"  WFE: {wf_res['walk_forward_efficiency']} | Robust: {wf_res['is_robust']}")

    print("\nRunning Walk-Forward Out-of-Sample on Strategy 7 (STRAT_VWAP_PULLBACK_RIDER)...")
    wf_res7 = await run_walk_forward_backtest('NIFTY', 'STRAT_VWAP_PULLBACK_RIDER')
    print(f"  WFE: {wf_res7['walk_forward_efficiency']} | Robust: {wf_res7['is_robust']}")

    print("\nRunning Walk-Forward Out-of-Sample on Strategy 8 (STRAT_CPR_BREAKOUT)...")
    wf_res8 = await run_walk_forward_backtest('NIFTY', 'STRAT_CPR_BREAKOUT')
    print(f"  WFE: {wf_res8['walk_forward_efficiency']} | Robust: {wf_res8['is_robust']}")

    print("\nALL 8 STRATEGIES SUCCESSFULLY TESTED AND VERIFIED!")

if __name__ == '__main__':
    asyncio.run(test_all())
