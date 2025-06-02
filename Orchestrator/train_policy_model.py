import numpy as np
import pandas as pd
from sklearn.svm import OneClassSVM
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
import joblib

# Define the components and their distributions
components = {
    'GRAYSCALER': {
        'mean_replica_count': 1, 'var_replica_count': 0,
        'mean_cpu_limit': 100, 'var_cpu_limit': 0,
        'mean_memory_limit': 256, 'var_memory_limit': 0
    },
    'COMPRESSOR': {
        'mean_replica_count': 1, 'var_replica_count': 0,
        'mean_cpu_limit': 100, 'var_cpu_limit': 0,
        'mean_memory_limit': 256, 'var_memory_limit': 0
    }
}

# Function to generate synthetic training data
def generate_data_for_component(n_samples, name, stats):
    replica_count = np.random.normal(stats['mean_replica_count'], np.sqrt(stats['var_replica_count']), n_samples).astype(int)
    cpu_limit = np.random.normal(stats['mean_cpu_limit'], np.sqrt(stats['var_cpu_limit']), n_samples)
    memory_limit = np.random.normal(stats['mean_memory_limit'], np.sqrt(stats['var_memory_limit']), n_samples)

    return pd.DataFrame({
        'replica_count': replica_count,
        'cpu_limit': cpu_limit,
        'memory_limit': memory_limit,
        'network_function': name
    })

# Generate training data
dataframes = [
    generate_data_for_component(100, name, stats)
    for name, stats in components.items()
]

training_data = pd.concat(dataframes, ignore_index=True)

# Define preprocessing
preprocessor = ColumnTransformer(transformers=[
    ('num', StandardScaler(), ['replica_count', 'cpu_limit', 'memory_limit']),
    ('cat', OneHotEncoder(), ['network_function'])
])

X_train = preprocessor.fit_transform(training_data)

# Train One-Class SVM
model = OneClassSVM(gamma=1, nu=0.001)
model.fit(X_train)


joblib.dump(model, 'ocsvm_model.pkl')
joblib.dump(preprocessor, 'preprocessor.pkl')

print("Model and preprocessor saved: 'ocsvm_model.pkl', 'preprocessor.pkl'")
