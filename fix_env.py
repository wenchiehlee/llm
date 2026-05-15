
key_value = "@#$^*%^&*%^(^&*)^&*&*OTYUJDFGNFBSERTWE$TWSRGS"
with open('.env', 'r', encoding='utf-8') as f:
    lines = f.readlines()
with open('.env', 'w', encoding='utf-8') as f:
    for line in lines:
        if line.startswith('CODEX_API_KEY='):
            f.write(f"CODEX_API_KEY='{key_value}'\n")
        else:
            f.write(line)
