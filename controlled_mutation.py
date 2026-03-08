import random
from dataclasses import dataclass
from typing import List, Optional, Tuple, Any
from enum import Enum, auto
import numpy as np

class MutationType(Enum):
    SINGLE_POINT = auto()
    MULTI_POINT = auto()
    UNIFORM = auto()
    GAUSSIAN = auto()
    CREATIVE = auto()

@dataclass
class MutationConfig:
    def __init__(self, mutation_rate: Optional[float] = None, 
                 num_points: Optional[int] = None, 
                 std_dev: Optional[float] = None):
        if mutation_rate is not None:
            self.mutation_rate = mutation_rate
        self.mutation_rate = self.mutation_rate or 0.1
        
        if num_points is not None:
            self.num_points = num_points
        self.num_points = self.num_points or 2
        
        if std_dev is not None:
            self.std_dev = std_dev
        self.std_dev = self.std_dev or 0.5
    mutation_rate: float = 0.1
    num_points: int = 2
    std_dev: float = 0.5

class RiskAssessment:
    @staticmethod
    def calculate_risk(current_state, proposed_state) -> Tuple[float, dict]:
        risk_score = 0.0
        assessment = {'total_risk': 0.0, 'components': {}}

        # State difference risk
        difference = abs(hash(tuple(current_state)) - hash(tuple(proposed_state)))
        assessment['components']['state_difference'] = difference
        if difference > 1000:
            risk_score += 0.7

        # Stability check
        try:
            stability = self._evaluate_stability(proposed_state)
            assessment['components']['stability'] = stability
            if stability < 0.5:
                risk_score += 0.3
        except Exception:
            assessment['components']['stability'] = 'error'

        risk_score = min(risk_score, 1.0)
        assessment['total_risk'] = risk_score
        return risk_score

    def _evaluate_stability(self, state):
        # Simple stability metric - would be more complex in practice
        return random.uniform(0.4, 0.9)

class Mutator:
    def __init__(self, config: Optional[MutationConfig] = None):
        self.config = config or MutationConfig()

    def mutate(self, individual: List[Any]) -> List[Any]:
        raise NotImplementedError

    def should_mutate(self) -> bool:
        return random.random() < self.config.mutation_rate

class SinglePointMutator(Mutator):
    def mutate(self, individual: List[Any]) -> List[Any]:
        mutated = individual.copy()
        point = random.randint(0, len(mutated) - 1)
        mutated[point] = self._mutate_value(mutated[point])
        return mutated

    def _mutate_value(self, value):
        if isinstance(value, int):
            return value + random.randint(-1, 1)
        elif isinstance(value, float):
            return value + random.uniform(-0.5, 0.5)
        return value

class MultiPointMutator(Mutator):
    def mutate(self, individual: List[Any]) -> List[Any]:
        mutated = individual.copy()
        points_to_mutate = min(self.config.num_points, len(mutated))
        for _ in range(points_to_mutate):
            point = random.randint(0, len(mutated) - 1)
            mutated[point] = self._mutate_value(mutated[point])

        return mutated

    def _mutate_value(self, value):
        mutation_types = [
            lambda v: v + random.randint(-2, 2) if isinstance(v, int) else v,
            lambda v: v + random.uniform(-1.0, 1.0) if isinstance(v, float) else v,
            lambda v: not v if isinstance(v, bool) else v
        ]
        return random.choice(mutation_types)(value)

class UniformMutator(Mutator):
    def mutate(self, individual: List[Any]) -> List[Any]:
        mutated = []
        for value in individual:
            if random.random() < self.config.mutation_rate:
                mutated.append(self._mutate_value(value))
            else:
                mutated.append(value)
        return mutated

    def _mutate_value(self, value):
        if isinstance(value, bool):
            return random.choice([True, False])
        return super()._mutate_value(value)

class GaussianMutator(Mutator):
    def mutate(self, individual: List[Any]) -> List[Any]:
        mutated = individual.copy()
        for i in range(len(mutated)):
            if random.random() < self.config.mutation_rate:
                mutated[i] += np.random.normal(0, self.config.std_dev)
        return mutated

class CreativeMutator(Mutator):
    def __init__(self, config: MutationConfig, risk_assessor: RiskAssessment):
        super().__init__(config)
        self.risk_assessor = risk_assessor

    def mutate(self, individual: List[Any]) -> Tuple[List[Any], dict]:
        original_hash = hash(tuple(individual))
        candidates = self._generate_candidates(individual)
        assessed = self._assess_candidates(candidates, individual)
        return self._select_lowest_risk(assessed), {'original_hash': original_hash}

    def _generate_candidates(self, individual):
        strategies = [
            SinglePointMutator(),
            MultiPointMutator(),
            UniformMutator(),
            GaussianMutator()
        ]
        return [strat.mutate(individual.copy()) for strat in strategies]

    def _assess_candidates(self, candidates, original):
        return [
            (
                self.risk_assessor.calculate_risk(original, cand)[0],
                cand,
                f'Risk: {self.risk_assessor.calculate_risk(original, cand)[0]:.2f}'
            ) for cand in candidates
        ]

    def _select_lowest_risk(self, assessed):
        assessed.sort(key=lambda x: x[0])
        return assessed[0][1]

def main():
    config = MutationConfig(mutation_rate=0.3, std_dev=0.8)
    risk_assessor = RiskAssessment()

    initial_individual = [42, True, 3.14, 'hello', False]
    print(f"Original: {initial_individual}")
    print("-" * 50)

    print("\nSingle Point Mutation:")
    single_result = SinglePointMutator(config).mutate(initial_individual.copy())
    print(f'Result: {single_result}')
    print(f'Risk: {risk_assessor.calculate_risk(initial_individual, single_result)[0]:.2f}')

    print("\nMulti-Point Mutation:")
    multi_result = MultiPointMutator(config).mutate(initial_individual.copy())
    print(f'Result: {multi_result}')
    print(f'Risk: {risk_assessor.calculate_risk(initial_individual, multi_result)[0]:.2f}')

    print("\nUniform Mutation:")
    uniform_result = UniformMutator(config).mutate(initial_individual.copy())
    print(f'Result: {uniform_result}')
    print(f'Risk: {risk_assessor.calculate_risk(initial_individual, uniform_result)[0]:.2f}')

if __name__ == "__main__":
    main()