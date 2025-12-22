import os
import random
from datetime import datetime
from api_fuzz_env import APIFuzzEnv
from q_learning_agent import QLearningAgent

# Parameters
episodes = 300
steps_per_episode = 10
repeats = 10
base_log_dir = "./experiment_logs"

def get_log_path(api_name, mode, run_id):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_path = os.path.join(base_log_dir, api_name, mode)
    os.makedirs(dir_path, exist_ok=True)
    return os.path.join(dir_path, f"run_{run_id}_{timestamp}.jsonl")

def run_experiment(api_name, mode, run_id):
    log_path = get_log_path(api_name, mode, run_id)

    #use_scores = True if mode == "heuristic" else False
    env = APIFuzzEnv(use_auth=False, log_file_path=log_path, use_endpoint_scores=False)
    mutation_agent = QLearningAgent(n_actions=len(env.mutation_actions)) if mode != "classic" else None
    endpoint_agent = QLearningAgent(n_actions=len(env.templates)) if mode == "rl" else None

    for ep in range(episodes):
        if mode == "rl":
            endpoint_state_template = random.choice(env.templates)
            endpoint_state = endpoint_state_template.get('endpoint', endpoint_state_template['url'])
            template_index = endpoint_agent.select_action(endpoint_state)
            env.current_template = env.templates[template_index]
        else:
            env.current_template = random.choice(env.templates)
            endpoint_state = env.current_template.get('endpoint', env.current_template['url'])  # fallback gdyby nie było endpoint

        template = env.current_template
        state = f"{template['method']}:{template['url']}:start"

        for step in range(steps_per_episode):
            if mode == "classic":
                action = random.randint(0, len(env.mutation_actions) - 1)
            else:
                action = mutation_agent.select_action(state)
            env.current_run = run_id
            env.current_episode = ep
            env.current_step = step

            next_template, reward, done, info = env.step(action)
            next_state = f"{next_template['method']}:{next_template['url']}:{info['status_code']}"
            if mode != "classic":
                mutation_agent.update(state, action, reward, next_state)
            if mode == "rl":
                endpoint_reward = 1 if reward >= 0.5 else -1
                endpoint_agent.update(endpoint_state, template_index, endpoint_reward, endpoint_state)

            if done:
                break
            state = next_state

def main():
    api_name = "petstore-localhost"
    mode = "classic"  # "classic", "heuristic", "rl"

    for run_id in range(repeats):
        print(f"\n🚀 Start run {run_id + 1}/{repeats} [{mode.upper()}]")
        run_experiment(api_name, mode, run_id)

if __name__ == "__main__":
    main()
