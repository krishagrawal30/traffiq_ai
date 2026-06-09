import sys
modules = [
    'simulation.engine',
    'agents.orchestrator',
    'agents.signal_optimizer',
    'agents.route_recommender',
    'agents.emergency_priority',
    'visualization.generate_video'
]
errors = False
for m in modules:
    try:
        __import__(m)
        print(f"{m} OK")
    except Exception as e:
        print(f"{m} ERROR: {e!r}")
        errors = True
if errors:
    sys.exit(1)
print('ALL IMPORTS OK')
