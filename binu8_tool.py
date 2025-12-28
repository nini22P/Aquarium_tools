import struct
import os
import csv
import argparse

def get_files(directory):
    file_list = []
    for root, dirs, files in os.walk(directory):
        for name in files:
            if not name.endswith('.binu8'):
                continue
            if name == '__global.binu8':
                continue
            file_list.append(os.path.join(root, name))
    return file_list

def byte2int(data):
    return struct.unpack('<L', data)[0]

def parse_header(src):
    src.seek(0)
    version = src.read(9)
    
    # does it start with version (no length prefix)
    if version[0] == 0x56 and version[1] == 0x45 and version[2] == 0x52: # VER
        src.seek(9, 0)
        unk_count = byte2int(src.read(4))
        src.seek(unk_count * 4, 1)
    # does it start with version (length prefixed)
    elif version[0] == 9 and version[4] == 0x56 and version[5] == 0x45 and version[6] == 0x52:
        src.seek(13, 0)
        unk_count = byte2int(src.read(4))
        src.seek(unk_count * 4, 1)
    # if it doesnt start with version
    else:
        src.seek(0)

    # Skip Init Code
    init_code_count = byte2int(src.read(4))
    src.seek(init_code_count * 8, 1)
    
    # Skip Code
    code_count = byte2int(src.read(4))
    src.seek(code_count * 8, 1)
    
    return src.tell()

def read_string_entry(src):
    """
    Reads a string entry from the source.
    Format: [Length (4 bytes)] + [String Data]
    Note: The Length usually includes the null terminator.
    """
    len_bytes = src.read(4)
    if not len_bytes:
        return None
    
    length = byte2int(len_bytes)
    
    if length > 0:
        content = src.read(length)
        if content and content[-1] == 0:
            return content[:-1].decode('utf-8', errors='replace')
        return content.decode('utf-8', errors='replace')
    
    return ""

def write_string_entry(dst, text):
    """
    Writes a string entry to the destination.
    Format: [Length (4 bytes)] + [String Data] + [Null Byte]
    Length = len(text_bytes) + 1 (for null)
    """
    encoded_str = text.encode('utf-8')
    dst.write(struct.pack('<L', len(encoded_str) + 1))
    dst.write(encoded_str)
    dst.write(b'\x00')

def dump_script(script_path, csv_path):
    files = get_files(script_path)
    print(f"Processing {len(files)} files...")
    
    rows = []
    
    for fn in files:
        with open(fn, 'rb') as src:
            str_offset = parse_header(src)
            
            src.seek(str_offset)
            str_count = byte2int(src.read(4))
            
            src.seek(5, 1)
            
            rel_path = os.path.relpath(fn, script_path).replace("\\", "/")

            for i in range(str_count - 1):
                text = read_string_entry(src)
                if text is not None:
                    text_sanitized = text.replace('\n', '\\n').replace('\r', '\\r')
                    rows.append({
                        'file': rel_path,
                        'id': i,
                        'original': text_sanitized,
                        'translation': '',
                    })

    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['file', 'id', 'original', 'translation']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Dumped to {csv_path}")

def import_script(script_path, csv_path, new_script_path):
    translation_map = {}
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                fname = row['file']
                idx = int(row['id'])
                trans = row['translation']
                trans = trans.replace('\\n', '\n').replace('\\r', '\r')
                
                if fname not in translation_map:
                    translation_map[fname] = {}
                translation_map[fname][idx] = trans
    else:
        print("CSV file not found. Proceeding to repack using original strings.")

    files = get_files(script_path)
    print(f"Importing into {len(files)} files...")

    for fn in files:
        rel_path = os.path.relpath(fn, script_path).replace("\\", "/")
        dst_path = os.path.join(new_script_path, rel_path)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        
        with open(fn, 'rb') as src, open(dst_path, 'wb') as dst:
            str_offset = parse_header(src)
            
            src.seek(0)

            header_size = str_offset + 9
            dst.write(src.read(header_size))
            
            src.seek(str_offset)
            str_count = byte2int(src.read(4))
            
            src.seek(5, 1) 
            
            current_file_map = translation_map.get(rel_path, {})
            
            for i in range(str_count - 1):
                original_text = read_string_entry(src)
                trans_text = current_file_map.get(i)
                
                if trans_text:
                    text_to_write = trans_text
                else:
                    text_to_write = original_text
                
                write_string_entry(dst, text_to_write)

            dst.write(src.read())

    print(f"Done. Output saved to {new_script_path}")

def main():
    parser = argparse.ArgumentParser(description="Tool for dumping and importing .binu8 script files.")
    subparsers = parser.add_subparsers(dest='command', required=True)

    p_dump = subparsers.add_parser('dump', help='Export strings to CSV')
    p_dump.add_argument('script_folder_path', help='Directory containing original .binu8 files')
    p_dump.add_argument('outupt_csv_path', help='Output CSV file path')

    p_import = subparsers.add_parser('import', help='Import strings from CSV')
    p_import.add_argument('script_folder_path', help='Directory containing original .binu8 files')
    p_import.add_argument('input_csv_path', help='Input CSV file path')
    p_import.add_argument('output_script_folder_path', help='Directory to save new .binu8 files')

    args = parser.parse_args()

    if args.command == 'dump':
        dump_script(args.script_folder_path, args.outupt_csv_path)
    elif args.command == 'import':
        import_script(args.script_folder_path, args.input_csv_path, args.output_script_folder_path)

if __name__ == '__main__':
    main()