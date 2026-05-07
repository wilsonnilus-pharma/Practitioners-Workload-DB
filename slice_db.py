# Save this as slice_db.py and run it on your computer
import os

chunk_size = 20 * 1024 * 1024  # 20 MB chunks
input_file = "PractitionersWorkloadDB.db"

with open(input_file, "rb") as f:
    chunk_num = 1
    while True:
        data = f.read(chunk_size)
        if not data:
            break
        
        output_file = f"db_part_{chunk_num}"
        with open(output_file, "wb") as out:
            out.write(data)
            print(f"Created {output_file}...")
        
        chunk_num += 1

print("Done! You can now upload these db_part_ files to GitHub.")