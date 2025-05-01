import pdfplumber
import pandas as pd

def extract_data_from_pdf(pdf_path):
    """
    Extract student data from the given PDF file.
    Assumes the PDF contains a table with 'Name' and 'Marks' columns.
    """
    with pdfplumber.open(pdf_path) as pdf:
        first_page = pdf.pages[0]
        table = first_page.extract_table()

    # Convert the table into a DataFrame (skip the header row)
    data = table[1:]  # Skip the first row (header)
    df = pd.DataFrame(data, columns=['Name', 'Marks'])
    
    # Convert 'Marks' to numeric values
    df['Marks'] = pd.to_numeric(df['Marks'], errors='coerce')
    
    return df

def classify_students(marksheet_path, threshold):
    """
    Classify students into two groups based on the threshold.
    
    :param marksheet_path: Path to the PDF marksheet.
    :param threshold: The marks threshold to classify students.
    :return: Two DataFrames: group_A (Above Threshold), group_B (Below Threshold).
    """
    # Extract data from the PDF
    df = extract_data_from_pdf(marksheet_path)
    
    # Ensure we have 'Marks' column
    if 'Marks' not in df.columns:
        raise ValueError("Marks column not found in the PDF. Please check your file.")

    # Create a 'Result' column based on threshold
    df['Result'] = df['Marks'].apply(lambda x: 'Above Threshold' if x >= threshold else 'Below Threshold')

    # Split the dataframe into two groups
    group_A = df[df['Marks'] >= threshold]
    group_B = df[df['Marks'] < threshold]
    
    # Return the two groups
    return group_A, group_B

# Example Usage:
marksheet_path = 'marksheet.pdf'  # Replace with your PDF path
threshold = float(input("Enter the threshold marks: "))

group_A, group_B = classify_students(marksheet_path, threshold)

print("\n=== Students Above or Equal to Threshold ===")
print(group_A[['Name', 'Marks']])

print("\n=== Students Below Threshold ===")
print(group_B[['Name', 'Marks']])

# Optionally save them as CSVs
group_A.to_csv('students_above_threshold.csv', index=False)
group_B.to_csv('students_below_threshold.csv', index=False)

print("\nSeparate marksheets saved successfully!")
