# Intelligent REST API Fuzzing with Reinforcement Learning and LLM Support

This repository contains an experimental framework for **automated REST API testing** that combines **reinforcement learning (Q‑Learning)** with **large language model (LLM) support** for semantic request generation.  
The project was developed as part of a **Master’s thesis** focused on applying artificial intelligence to software testing automation.

## Project Overview

Modern REST APIs expose large and complex input spaces, making traditional random or heuristic-based fuzzing approaches inefficient.  
This project proposes a **hybrid, adaptive testing system** that integrates:

- **Two reinforcement learning agents**
- **Semantic request template generation using GPT**
- **Dynamic mutation and endpoint prioritization**
- **Automated experiment logging and hypothesis analysis**

The goal is to evaluate whether intelligent, learning-based strategies outperform classical random fuzzing in terms of **fault detection effectiveness** and **exploration efficiency**.

---

## System Architecture

The system consists of the following core components:

### 1. GPT-based Request Template Generator
A large language model (GPT) is used to:
- Parse OpenAPI / Swagger documentation
- Generate **initial, semantically valid request templates**
- Extract parameter constraints and contextual information

These templates form the **initial state space** for the reinforcement learning agents and significantly reduce the cold-start problem compared to purely random fuzzing.

---

### 2. Reinforcement Learning Agents

The framework uses **two independent Q-Learning agents**, each responsible for a different decision layer:

#### Agent 1: Mutation Selection Agent
- Learns which **mutation operators** (e.g. value corruption, boundary mutation, semantic mutation) are most effective
- Reward signal is based on:
  - HTTP 5XX responses
  - Unexpected server behavior
  - Novel execution paths (when available)

#### Agent 2: Endpoint Selection Agent
- Learns which **API endpoints** should be prioritized during testing
- Dynamically adapts exploration strategy based on historical effectiveness
- Helps focus testing effort on endpoints more prone to failures

Both agents operate using **Q‑Learning**, maintaining separate Q‑tables and reward histories.

---

### 3. Fuzzing and Execution Engine
- Combines selected endpoint + mutation strategy
- Sends generated HTTP requests to the System Under Test (SUT)
- Captures responses, status codes, and metadata
- Feeds results back to both RL agents

---

### 4. Experiment Logging and Analysis

After execution, the system automatically generates:

- `experiment_logs/`
  - Raw execution logs
  - Per‑episode rewards
  - Endpoint and mutation usage statistics

A dedicated analysis script:
- `analyze_hypothesis.py`

Processes these logs to:
- Aggregate results
- Compare strategies (random vs heuristic vs RL-based)
- Verify research hypotheses defined in the thesis

---

## Experimental Setup

The framework supports comparative evaluation of three strategies:

1. **Fully Random**
   - Random endpoint selection
   - Random mutation selection

2. **Heuristic Endpoint + RL Mutation**
   - Endpoint prioritization based on observed failures
   - Mutation selection learned via Q‑Learning

3. **Full RL (Endpoint + Mutation)**
   - Both endpoint selection and mutation selection learned via Q‑Learning

Experiments are conducted using fixed numbers of episodes and steps to ensure fair comparison.

---

## Key Findings (Summary)

Based on conducted experiments:

- RL‑based strategies generated **more HTTP 5XX errors** than random fuzzing
- Endpoint prioritization significantly improved early fault discovery
- Semantic mutations (LLM‑assisted) outperformed purely random mutations
- Dual‑agent RL achieved the **best balance between exploration and exploitation**

These results support the hypothesis that **reinforcement learning combined with semantic knowledge improves REST API testing effectiveness**.

---

## How to Run

### Requirements
- Python 3.9+
- OpenAI API key (for GPT integration)
- Internet access to the tested REST API or REST API is hosted locally
- Generated token for API usage

### Execution
```bash
python main.py
