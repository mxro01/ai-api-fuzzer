import os
import json
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import hashlib

base_log_dir = Path("./experiment_logs")
output_dir = Path("./analysis_output")

def load_all_logs(api_name, mode):
    logs = []
    log_dir = base_log_dir / api_name / mode
    if not log_dir.exists():
        print(f"Directory not found: {log_dir}")
        return pd.DataFrame()

    for file in log_dir.glob("run_*.jsonl"):
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    logs.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
    return pd.DataFrame(logs)

def hash_response(text):
    if not text:
        return "empty"
    return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()

def analyze_logs_extended(df, api_name, mode):
    if df.empty:
        return

    output_path = output_dir / api_name / mode
    os.makedirs(output_path, exist_ok=True)

    df["__endpoint"] = df["original_request"].apply(lambda x: x.get("endpoint") if isinstance(x, dict) else None)
    df["__path"] = df["mutated_request"].apply(lambda x: x.get("path") if isinstance(x, dict) else None)

    summary = {
        "total_requests": len(df),
        "unique_endpoints": df["__endpoint"].nunique(),
        "unique_mutators": df["action_name"].nunique() if "action_name" in df else None,
        "avg_reward": df["reward"].mean(),
        "reward_std": df["reward"].std(),
        "total_5xx": df[df["status_code"] >= 500].shape[0],
        "total_4xx": df[(df["status_code"] >= 400) & (df["status_code"] < 500)].shape[0],
        "total_2xx": df[(df["status_code"] >= 200) & (df["status_code"] < 300)].shape[0],
        "unique_status_codes": df["status_code"].nunique(),
        "unique_paths_tested": df["__path"].nunique()
    }
    df["__bug_id"] = df.apply(
        lambda row: f"{row.get('__endpoint')}|{row.get('status_code')}|{hash_response(row.get('response_text', ''))}"
        if row.get("status_code", 0) >= 500 and row.get("response_diff")
        else None,
        axis=1
    )
    unique_bugs = df["__bug_id"].dropna().nunique()
    summary["unique_bugs_found"] = unique_bugs

    if {"run", "episode"}.issubset(df.columns):
        first_5xx = df[df["status_code"] >= 500].groupby("run")["episode"].min()
        summary["avg_episode_to_first_5xx"] = first_5xx.mean()
        summary["runs_with_5xx"] = first_5xx.count()
        first_5xx.plot(marker='o')
        plt.title("Episode to first 5xx error (per run)")
        plt.xlabel("Run ID")
        plt.ylabel("Episode")
        plt.grid(True)
        plt.savefig(output_path / "episode_to_first_5xx.png")
        plt.clf()

    reward_by_mutator = df.groupby("action_name")["reward"].agg(["count", "mean", "std"]).sort_values(by="mean", ascending=False)
    if "mutation_type" in df.columns:
        reward_by_type = df.groupby("mutation_type")["reward"].agg(["count", "mean", "std"]).sort_values(by="mean", ascending=False)
        errors_by_type = df[df["status_code"] >= 500].groupby("mutation_type")["status_code"].count()

        reward_by_type.to_csv(output_path / "reward_by_mutation_type.csv")
        errors_by_type.to_csv(output_path / "errors_by_mutation_type.csv")

        reward_by_type["mean"].plot(kind="barh", title="Average reward per mutation type", figsize=(10, 6))
        plt.ylabel("Typ mutacji")
        plt.xlabel("Średnia nagroda")
        plt.tight_layout()
        plt.savefig(output_path / "reward_per_mutation_type.png")
        plt.clf()

        errors_by_type.plot(kind="bar", title="Amount of server errors (5XX) per mutation type", figsize=(10, 6))
        plt.ylabel("5XX errors summary")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(output_path / "errors_per_mutation_type.png")
        plt.clf()

    error_by_endpoint = df[df["status_code"] >= 500]["__endpoint"].value_counts()

    reward_by_mutator["mean"].plot(kind="barh", title="Average reward per mutation operator", figsize=(10, 6))
    plt.ylabel("Operator")
    plt.xlabel("Average reward")
    plt.tight_layout()
    plt.savefig(output_path / "reward_per_mutator.png")
    plt.clf()

    error_by_endpoint.head(10).plot(kind="bar", title="Most failing endpoints (5xx)")
    plt.ylabel("Amount of 5XX errors")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_path / "errors_per_endpoint.png")
    plt.clf()
    pd.DataFrame.from_dict(summary, orient="index", columns=["value"]).to_csv(output_path / "summary.csv")
    reward_by_mutator.to_csv(output_path / "reward_by_mutator.csv")
    error_by_endpoint.to_csv(output_path / "errors_by_endpoint.csv")

api_name = "crapi"
mode = "heuristic"  # classic / heuristic / rl

print(f"\nAnalysis: {api_name.upper()} [{mode.upper()}]")

df_logs = load_all_logs(api_name, mode)
analyze_logs_extended(df_logs, api_name, mode)

print(f"Charts and tables saved in: {output_dir / api_name / mode}")
