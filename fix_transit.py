import sys

file_path = 'backend/app/services/transit_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if line.startswith('    def get_trip_stops(self, feed_name: str, trip_id: str) -> list["TripStop"]:') and i < 1000:
        skip = True
    if skip and line.startswith('    def find_transfer_routes'):
        skip = False
    if not skip:
        new_lines.append(line)

# Now fix the get_direct_journeys to include departure_display
code = ''.join(new_lines)
target = '''                        departure_time=departure_time,
                        arrival_time=arrival_time,
                        duration_minutes=duration_minutes,
                        shape_id=shape_id,'''
replacement = '''                        departure_time=departure_time,
                        arrival_time=arrival_time,
                        departure_display=parse_gtfs_time_to_display(departure_time),
                        arrival_display=parse_gtfs_time_to_display(arrival_time),
                        duration_minutes=duration_minutes,
                        shape_id=shape_id,'''

if target in code:
    code = code.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(code)
    print('File patched successfully.')
else:
    print('Target not found!')
