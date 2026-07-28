import pandas as pd
from pathlib import Path
p = Path('EOR_Screening_Tool_2026.xlsx')
print('exists', p.exists())
if p.exists():
    xl = pd.ExcelFile(p)
    print('sheets', xl.sheet_names)
    for s in xl.sheet_names:
        df = pd.read_excel(p, sheet_name=s)
        print('\nSHEET', s, 'shape', df.shape)
        print(df.head(3).to_string(index=False))
        print('columns', list(df.columns)[:30])
