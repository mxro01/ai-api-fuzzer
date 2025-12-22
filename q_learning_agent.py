import numpy as np
import random
#discount na poczatku bylo 0.95, zmienione na 0.99
class QLearningAgent:
    def __init__(self, n_actions, learning_rate=0.1, discount=0.99 , epsilon=1.0, epsilon_decay=0.997, min_epsilon=0.1): #bylo 0.99 i 0.05
        self.q_table = {}  # dict[state] = np.array[n_actions]
        self.n_actions = n_actions
        self.lr = learning_rate
        self.gamma = discount
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.min_epsilon = min_epsilon

    def get_qs(self, state):
        if state not in self.q_table:
            self.q_table[state] = np.zeros(self.n_actions)
        return self.q_table[state]

    def select_action(self, state):
        if random.random() < self.epsilon:
            return random.randint(0, self.n_actions - 1)
        return int(np.argmax(self.get_qs(state)))

    def update(self, state, action, reward, next_state):
        current_q = self.get_qs(state)[action]
        max_future_q = np.max(self.get_qs(next_state))
        new_q = (1 - self.lr) * current_q + self.lr * (reward + self.gamma * max_future_q)
        self.q_table[state][action] = new_q
        self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)
