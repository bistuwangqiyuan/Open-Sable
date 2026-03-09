import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

class ProbabilityDistribution:
    """Base class for probability distributions."""
    
    def __init__(self, data):
        self.data = data
        self.n_samples = len(data)
        
    def calculate_mean(self):
        """Compute the mean of the distribution."""
        return np.mean(self.data)
    
    def calculate_variance(self):
        """Compute the variance of the distribution."""
        return np.var(self.data)
    
    def plot_distribution(self, title='Distribution'):
        """Visualize the probability distribution."""
        plt.hist(self.data, bins=30, alpha=0.7, edgecolor='black')
        plt.title(title)
        plt.xlabel('Value')
        plt.ylabel('Frequency')
        plt.grid(True)
        plt.show()


class SymmetryValidator:
    """Class for validating symmetry in distributions."""
    
    def __init__(self, distribution):
        self.distribution = distribution
        
    def test_radial_symmetry(self, center=None, samples=1000):
        """Test for radial symmetry around a center point."""
        if center is None:
            center = np.mean(self.distribution.data)
        
        # Generate random angles
        theta = np.random.uniform(0, 2*np.pi, samples)
        r = np.sqrt((self.distribution.data - center)**2)
        
        # Check if points at distance r from center are equally likely in all directions
        symmetry_score = np.mean([np.any(r == np.abs(center + r * np.cos(theta[i]))) 
                                 for i in range(samples)])
        
        return {
            'test': 'radial_symmetry',
            'center': center,
            'symmetry_score': symmetry_score,
            'is_symmetric': symmetry_score > 0.5
        }
    
    def test_mirror_symmetry(self, axis=0):
        """Test for mirror (reflection) symmetry across an axis."""
        # For discrete data, check if data mirrored around axis matches original
        mirrored_data = np.flip(self.distribution.data, axis=axis)
        
        # Use statistical test to compare original vs mirrored data
        t_statistic, p_value = stats.ttest_ind(
            self.distribution.data, mirrored_data, equal_var=False)
        
        return {
            'test': 'mirror_symmetry',
            'axis': axis,
            't_statistic': t_statistic,
            'p_value': p_value,
            'is_symmetric': p_value > 0.05
        }
    
    def validate_probabilistic_symmetry(
        self, threshold=0.95, verbose=True):
        """Validate probabilistic symmetry with confidence threshold."""
        
        results = {
            'radial_test': self.test_radial_symmetry(),
            'mirror_test': self.test_mirror_symmetry()
        }
        
        # Aggregate results based on threshold
        is_symmetric = all(r['is_symmetric'] for r in results.values())
        
        if verbose:
            print(f"Symmetry Validation Results:")
            for test_name, result in results.items():
                print(f"  {test_name}: {result}")
                print(f"    {'✓ Symmetric' if result['is_symmetric'] else '✗ Asymmetric'}")
        
        return {
            'framework': 'Probabilistic Symmetry Validator',
            'threshold': threshold,
            'results': results,
            'overall_symmetric': is_symmetric
        }

# Example usage:
def main():
    # Create sample distributions
    np.random.seed(42)
    symmetric_data = np.random.normal(loc=0, scale=1, size=1000)
    asymmetric_data = np.concatenate([
        np.random.normal(loc=-2, scale=1, size=500),
        np.random.normal(loc=2, scale=1, size=500)
    ])

    # Create validator instances
    sym_dist = ProbabilityDistribution(symmetric_data)
    asym_dist = ProbabilityDistribution(asymmetric_data)

    validator = SymmetryValidator(sym_dist)

    # Run validation
    print("\nRunning symmetry validation...")
    validation_result = validator.validate_probabilistic_symmetry(
        threshold=0.95, verbose=True)

    print(f"\nOverall symmetric: {validation_result['overall_symmetric']}")

if __name__ == '__main__':
    main()