import requests
import json

# Team abbreviations for the Thanksgiving weekend 2025 games
THANKSGIVING_TEAMS = {
    'GB': 'Green Bay Packers',
    'DET': 'Detroit Lions',
    'KC': 'Kansas City Chiefs',
    'DAL': 'Dallas Cowboys',
    'CIN': 'Cincinnati Bengals',
    'BAL': 'Baltimore Ravens',
    'CHI': 'Chicago Bears',
    'PHI': 'Philadelphia Eagles'
}

# ESPN API team IDs
ESPN_TEAM_IDS = {
    'GB': 9,
    'DET': 8,
    'KC': 12,
    'DAL': 6,
    'CIN': 4,
    'BAL': 33,
    'CHI': 3,
    'PHI': 21
}

def fetch_team_roster(team_abbr):
    """Fetch roster for a specific team from ESPN API"""
    team_id = ESPN_TEAM_IDS.get(team_abbr)
    if not team_id:
        return None
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/roster"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        players = []
        
        # Process athletes from roster
        for group in data.get('athletes', []):
            position_group = group.get('position', 'Unknown')
            for athlete in group.get('items', []):
                player_info = {
                    'name': athlete.get('displayName', ''),
                    'full_name': athlete.get('fullName', ''),
                    'jersey': athlete.get('jersey', ''),
                    'position': athlete.get('position', {}).get('abbreviation', ''),
                    'headshot': athlete.get('headshot', {}).get('href', ''),
                    'team': team_abbr,
                    'team_name': THANKSGIVING_TEAMS[team_abbr]
                }
                players.append(player_info)
        
        return players
    
    except Exception as e:
        print(f"Error fetching roster for {team_abbr}: {e}")
        return None

def fetch_all_rosters():
    """Fetch rosters for all Thanksgiving weekend teams"""
    all_players = []
    
    print("Fetching rosters for Thanksgiving weekend games...")
    print("=" * 60)
    
    for team_abbr in THANKSGIVING_TEAMS.keys():
        print(f"Fetching {THANKSGIVING_TEAMS[team_abbr]}...")
        roster = fetch_team_roster(team_abbr)
        if roster:
            all_players.extend(roster)
            print(f"  ✅ Found {len(roster)} players")
        else:
            print(f"  ❌ Failed to fetch roster")
    
    print("=" * 60)
    print(f"Total players: {len(all_players)}")
    
    return all_players

def save_rosters_to_json(players, filename='thanksgiving_rosters.json'):
    """Save roster data to JSON file"""
    with open(filename, 'w') as f:
        json.dump(players, f, indent=2)
    print(f"\n✅ Saved roster data to {filename}")

def create_player_lookup(players):
    """Create a searchable player lookup dictionary"""
    lookup = {}
    for player in players:
        # Create multiple keys for flexible searching
        name_lower = player['name'].lower()
        full_name_lower = player['full_name'].lower()
        
        key = f"{name_lower}|{player['team'].lower()}"
        lookup[key] = player
        
        # Also add full name variant
        full_key = f"{full_name_lower}|{player['team'].lower()}"
        lookup[full_key] = player
    
    return lookup

if __name__ == "__main__":
    # Fetch all rosters
    players = fetch_all_rosters()
    
    # Save to JSON
    save_rosters_to_json(players)
    
    # Create lookup dictionary and save
    lookup = create_player_lookup(players)
    with open('player_lookup.json', 'w') as f:
        json.dump(lookup, f, indent=2)
    print(f"✅ Saved player lookup to player_lookup.json")
    
    # Print some sample players with photos
    print("\n" + "=" * 60)
    print("Sample players with photos:")
    print("=" * 60)
    
    count = 0
    for player in players:
        if player['headshot'] and count < 10:
            print(f"{player['name']} ({player['team']}) - {player['position']}")
            print(f"  Photo: {player['headshot']}")
            count += 1
