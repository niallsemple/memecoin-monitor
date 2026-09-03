import json

d = json.load(open('xchain_outcomes.json'))
print('Total tracked:', len(d))
closed = [v for v in d.values() if v.get('status') == 'closed']
wins = [v for v in closed if v.get('ret', 0) > 0]
losses = [v for v in closed if v.get('ret', 0) <= 0]
print('Closed:', len(closed), '| Wins:', len(wins), '| Losses:', len(losses))
if closed:
    avg_ret = sum(v.get('ret', 0) for v in closed) / len(closed)
    win_rate = len(wins) / len(closed)
    print(f'Avg return: {avg_ret:.4f} | Win rate: {win_rate:.2%}')
    for v in closed[-3:]:
        print(f"  {v['chain']} {v['name']} -> {v['exit_reason']} ret={v.get('ret',0):.4f}")
