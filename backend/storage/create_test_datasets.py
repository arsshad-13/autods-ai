import pandas as pd
import os

storage_dir = os.path.dirname(os.path.abspath(__file__))

# 1. Create a valid CSV dataset
valid_data = {
    'employee_id': [101, 102, 103, 104, 105],
    'name': ['John Doe', 'Jane Smith', 'Bob Johnson', 'Alice Williams', 'Charlie Brown'],
    'department': ['Engineering', 'Marketing', 'Engineering', 'HR', 'Sales'],
    'salary': [85000, 62000, 95000, 58000, 70000],
    'hire_date': ['2021-03-15', '2022-01-10', '2020-11-01', '2023-05-20', '2021-08-01'],
    'is_active': [True, True, True, False, True]
}
df_valid = pd.DataFrame(valid_data)
valid_path = os.path.join(storage_dir, 'valid_employee_dataset.csv')
df_valid.to_csv(valid_path, index=False)
print(f"Created valid CSV at: {valid_path}")

# 2. Create a malformed CSV dataset
# A malformed CSV file with inconsistent column counts and parsing conflicts
malformed_content = """col1,col2,col3
val1,val2,val3
val4,val5
val6,val7,val8,val9,val10
val11,"unclosed quote string
"""
malformed_path = os.path.join(storage_dir, 'malformed_dataset.csv')
with open(malformed_path, 'w', encoding='utf-8') as f:
    f.write(malformed_content)
print(f"Created malformed CSV at: {malformed_path}")
