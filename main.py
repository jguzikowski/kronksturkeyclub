import discord
from discord.ext import commands
import json
import os
from datetime import datetime

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Data storage
DRAFT_DATA_FILE = 'draft_data.json'

class DraftManager:
    def __init__(self):
        self.base_draft_order = []  # Original order of users
        self.draft_order = []  # Full snake draft order
        self.current_pick = 0
        self.num_rounds = 0
        self.teams = {}  # {user_id: {name: str, players: []}}
        self.all_picks = []  # History of all picks
        self.is_active = False
        self.channel_id = None
        self.drafted_players = set()  # Track all drafted players to prevent duplicates
        self.load_data()
    
    def load_data(self):
        """Load draft data from file if it exists"""
        if os.path.exists(DRAFT_DATA_FILE):
            try:
                with open(DRAFT_DATA_FILE, 'r') as f:
                    data = json.load(f)
                    self.base_draft_order = data.get('base_draft_order', [])
                    self.draft_order = data.get('draft_order', [])
                    self.current_pick = data.get('current_pick', 0)
                    self.num_rounds = data.get('num_rounds', 0)
                    self.teams = data.get('teams', {})
                    self.all_picks = data.get('all_picks', [])
                    self.is_active = data.get('is_active', False)
                    self.channel_id = data.get('channel_id')
                    # Rebuild drafted players set
                    self.drafted_players = set()
                    for pick in self.all_picks:
                        player_key = f"{pick['player_name'].lower()}|{pick['player_team'].lower()}"
                        self.drafted_players.add(player_key)
            except Exception as e:
                print(f"Error loading data: {e}")
    
    def save_data(self):
        """Save draft data to file"""
        data = {
            'base_draft_order': self.base_draft_order,
            'draft_order': self.draft_order,
            'current_pick': self.current_pick,
            'num_rounds': self.num_rounds,
            'teams': self.teams,
            'all_picks': self.all_picks,
            'is_active': self.is_active,
            'channel_id': self.channel_id
        }
        with open(DRAFT_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    def create_snake_order(self, base_order, num_rounds):
        """Create snake draft order from base order"""
        snake_order = []
        for round_num in range(num_rounds):
            if round_num % 2 == 0:
                # Even rounds: normal order (0, 2, 4...)
                snake_order.extend(base_order)
            else:
                # Odd rounds: reverse order (1, 3, 5...)
                snake_order.extend(reversed(base_order))
        return snake_order
    
    def start_draft(self, base_order, num_rounds, channel_id):
        """Initialize a new snake draft"""
        self.base_draft_order = base_order
        self.num_rounds = num_rounds
        self.draft_order = self.create_snake_order(base_order, num_rounds)
        self.current_pick = 0
        self.teams = {user_id: {'name': f'Team {i+1}', 'players': []} 
                      for i, user_id in enumerate(base_order)}
        self.all_picks = []
        self.drafted_players = set()
        self.is_active = True
        self.channel_id = channel_id
        self.save_data()
    
    def is_player_drafted(self, player_name, player_team):
        """Check if a player has already been drafted"""
        player_key = f"{player_name.lower()}|{player_team.lower()}"
        return player_key in self.drafted_players
    
    def add_pick(self, player_name, player_team):
        """Record a draft pick"""
        if not self.is_active or self.current_pick >= len(self.draft_order):
            return None, "Draft is complete!"
        
        # Check for duplicate
        if self.is_player_drafted(player_name, player_team):
            return None, f"{player_name} ({player_team}) has already been drafted!"
        
        user_id = self.draft_order[self.current_pick]
        pick_info = {
            'player_name': player_name,
            'player_team': player_team,
            'pick_number': len(self.all_picks) + 1,
            'timestamp': datetime.now().isoformat()
        }
        
        self.teams[user_id]['players'].append(pick_info)
        self.all_picks.append({
            'user_id': user_id,
            **pick_info
        })
        
        # Add to drafted players set
        player_key = f"{player_name.lower()}|{player_team.lower()}"
        self.drafted_players.add(player_key)
        
        self.current_pick += 1
        self.save_data()
        
        return user_id, None
    
    def get_current_user(self):
        """Get the user ID who is currently on the clock"""
        if not self.is_active or self.current_pick >= len(self.draft_order):
            return None
        return self.draft_order[self.current_pick]
    
    def get_next_user(self):
        """Get the user ID who is on deck"""
        next_pick = self.current_pick + 1
        if not self.is_active or next_pick >= len(self.draft_order):
            return None
        return self.draft_order[next_pick]
    
    def undo_last_pick(self):
        """Undo the last draft pick"""
        if not self.all_picks:
            return False
        
        last_pick = self.all_picks.pop()
        user_id = last_pick['user_id']
        self.teams[user_id]['players'].pop()
        
        # Remove from drafted players set
        player_key = f"{last_pick['player_name'].lower()}|{last_pick['player_team'].lower()}"
        self.drafted_players.discard(player_key)
        
        self.current_pick -= 1
        self.save_data()
        return True
    
    def get_current_round(self):
        """Get the current round number"""
        if not self.base_draft_order:
            return 0
        return (self.current_pick // len(self.base_draft_order)) + 1
    
    def export_teams_for_scoring(self):
        """Export team data in format for scoring system"""
        export_data = []
        for user_id, team_data in self.teams.items():
            export_data.append({
                'team_name': team_data['name'],
                'user_id': user_id,
                'players': [
                    {
                        'name': p['player_name'],
                        'team': p['player_team']
                    }
                    for p in team_data['players']
                ]
            })
        return export_data

draft_manager = DraftManager()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is ready in {len(bot.guilds)} guild(s)')

@bot.command(name='startdraft')
async def start_draft(ctx, rounds: int, *user_mentions):
    """
    Start a new snake draft with the specified user order and number of rounds
    Usage: !startdraft 5 @User1 @User2 @User3 ...
    (This creates a 5-round snake draft)
    """
    if not user_mentions:
        await ctx.send("❌ Please provide number of rounds and mention users in draft order:\n`!startdraft 5 @User1 @User2 @User3`")
        return
    
    if rounds < 1 or rounds > 20:
        await ctx.send("❌ Number of rounds must be between 1 and 20!")
        return
    
    # Extract user IDs from mentions
    draft_order = [str(user.id) for user in ctx.message.mentions]
    
    if len(draft_order) < 2:
        await ctx.send("❌ Need at least 2 users for a draft!")
        return
    
    draft_manager.start_draft(draft_order, rounds, ctx.channel.id)
    
    # Create draft announcement
    order_text = "\n".join([f"{i+1}. <@{uid}>" for i, uid in enumerate(draft_order)])
    
    total_picks = len(draft_order) * rounds
    
    embed = discord.Embed(
        title="🏈 SNAKE DRAFT STARTED!",
        description=f"**Draft Order (Round 1):**\n{order_text}",
        color=discord.Color.green()
    )
    embed.add_field(name="Number of Rounds", value=str(rounds), inline=True)
    embed.add_field(name="Total Picks", value=str(total_picks), inline=True)
    embed.add_field(name="Current Pick", value="1", inline=True)
    embed.set_footer(text="🐍 Snake format: Order reverses each round!")
    
    await ctx.send(embed=embed)
    
    # Ping first user
    current_user_id = draft_manager.get_current_user()
    next_user_id = draft_manager.get_next_user()
    
    await ctx.send(f"🔔 <@{current_user_id}> - You're on the clock! (Round 1, Pick 1)\nMake your pick with `!pick PlayerName, TeamName`")
    if next_user_id:
        await ctx.send(f"⏭️ <@{next_user_id}> - You're on deck!")

@bot.command(name='pick')
async def make_pick(ctx, *, player_info):
    """
    Make a draft pick
    Usage: !pick Tom Brady, Buccaneers
    """
    if not draft_manager.is_active:
        await ctx.send("❌ No active draft! Start one with `!startdraft`")
        return
    
    current_user_id = draft_manager.get_current_user()
    
    if str(ctx.author.id) != current_user_id:
        await ctx.send(f"❌ It's not your turn! <@{current_user_id}> is on the clock.")
        return
    
    # Parse player info
    if ',' not in player_info:
        await ctx.send("❌ Format: `!pick PlayerName, TeamName`")
        return
    
    player_name, player_team = [x.strip() for x in player_info.split(',', 1)]
    
    # Record the pick
    user_id, error = draft_manager.add_pick(player_name, player_team)
    
    # Check for errors (duplicate or draft complete)
    if error:
        await ctx.send(f"❌ {error}")
        return
    
    pick_number = len(draft_manager.all_picks)
    current_round = draft_manager.get_current_round()
    pick_in_round = ((pick_number - 1) % len(draft_manager.base_draft_order)) + 1
    
    # Announcement
    embed = discord.Embed(
        title=f"Pick #{pick_number} (Round {current_round}, Pick {pick_in_round})",
        description=f"<@{ctx.author.id}> selects:",
        color=discord.Color.blue()
    )
    embed.add_field(name="Player", value=player_name, inline=True)
    embed.add_field(name="Team", value=player_team, inline=True)
    
    await ctx.send(embed=embed)
    
    # Check if draft is complete
    if draft_manager.current_pick >= len(draft_manager.draft_order):
        await ctx.send("🎉 **DRAFT COMPLETE!** Use `!teams` to see all rosters or `!export` to get data for scoring.")
        draft_manager.is_active = False
        draft_manager.save_data()
        return
    
    # Ping next user
    current_user_id = draft_manager.get_current_user()
    next_user_id = draft_manager.get_next_user()
    next_round = draft_manager.get_current_round()
    next_pick_in_round = ((draft_manager.current_pick) % len(draft_manager.base_draft_order)) + 1
    
    await ctx.send(f"🔔 <@{current_user_id}> - You're on the clock! (Round {next_round}, Pick {next_pick_in_round})\nMake your pick with `!pick PlayerName, TeamName`")
    if next_user_id:
        await ctx.send(f"⏭️ <@{next_user_id}> - You're on deck!")

@bot.command(name='teams')
async def show_teams(ctx):
    """Show all current team rosters"""
    if not draft_manager.teams:
        await ctx.send("❌ No draft data available!")
        return
    
    for user_id, team_data in draft_manager.teams.items():
        players_text = "\n".join([
            f"{i+1}. {p['player_name']} ({p['player_team']})" 
            for i, p in enumerate(team_data['players'])
        ]) or "No picks yet"
        
        embed = discord.Embed(
            title=f"<@{user_id}>'s Team",
            description=players_text,
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Total Players: {len(team_data['players'])}")
        
        await ctx.send(embed=embed)

@bot.command(name='myteam')
async def show_my_team(ctx):
    """Show your current roster"""
    user_id = str(ctx.author.id)
    
    if user_id not in draft_manager.teams:
        await ctx.send("❌ You're not in this draft!")
        return
    
    team_data = draft_manager.teams[user_id]
    players_text = "\n".join([
        f"{i+1}. {p['player_name']} ({p['player_team']})" 
        for i, p in enumerate(team_data['players'])
    ]) or "No picks yet"
    
    embed = discord.Embed(
        title="Your Team",
        description=players_text,
        color=discord.Color.purple()
    )
    embed.set_footer(text=f"Total Players: {len(team_data['players'])}")
    
    await ctx.send(embed=embed)

@bot.command(name='undo')
async def undo_pick(ctx):
    """Undo the last draft pick (admin only)"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Only administrators can undo picks!")
        return
    
    if draft_manager.undo_last_pick():
        await ctx.send("✅ Last pick undone!")
        
        # Notify current picker
        current_user_id = draft_manager.get_current_user()
        if current_user_id:
            await ctx.send(f"🔔 <@{current_user_id}> - You're back on the clock!")
    else:
        await ctx.send("❌ No picks to undo!")

@bot.command(name='export')
async def export_data(ctx):
    """Export draft data for the scoring system"""
    if not draft_manager.teams:
        await ctx.send("❌ No draft data available!")
        return
    
    export_data = draft_manager.export_teams_for_scoring()
    
    # Save to file
    filename = f'draft_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(filename, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    await ctx.send(
        "✅ Draft data exported! Copy this data into the scoring system:",
        file=discord.File(filename)
    )

@bot.command(name='setteamname')
async def set_team_name(ctx, *, team_name):
    """Set your team name"""
    user_id = str(ctx.author.id)
    
    if user_id not in draft_manager.teams:
        await ctx.send("❌ You're not in this draft!")
        return
    
    draft_manager.teams[user_id]['name'] = team_name
    draft_manager.save_data()
    
    await ctx.send(f"✅ Team name updated to: **{team_name}**")

@bot.command(name='status')
async def draft_status(ctx):
    """Show current draft status"""
    if not draft_manager.is_active:
        await ctx.send("❌ No active draft!")
        return
    
    current_user_id = draft_manager.get_current_user()
    next_user_id = draft_manager.get_next_user()
    total_picks = len(draft_manager.draft_order)
    picks_made = len(draft_manager.all_picks)
    current_round = draft_manager.get_current_round()
    
    embed = discord.Embed(
        title="📊 Draft Status",
        color=discord.Color.blue()
    )
    embed.add_field(name="Current Round", value=f"{current_round}/{draft_manager.num_rounds}", inline=True)
    embed.add_field(name="Picks Made", value=f"{picks_made}/{total_picks}", inline=True)
    embed.add_field(name="Format", value="🐍 Snake", inline=True)
    embed.add_field(name="On the Clock", value=f"<@{current_user_id}>", inline=False)
    if next_user_id:
        embed.add_field(name="On Deck", value=f"<@{next_user_id}>", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='commands')
async def help_command(ctx):
    """Show all available commands"""
    embed = discord.Embed(
        title="🏈 Fantasy Draft Bot Commands",
        description="Here are all available commands:",
        color=discord.Color.green()
    )
    
    commands_list = [
        ("!startdraft 5 @User1 @User2 ...", "Start snake draft with 5 rounds"),
        ("!pick PlayerName, TeamName", "Make your draft pick"),
        ("!myteam", "Show your current roster"),
        ("!teams", "Show all team rosters"),
        ("!setteamname Name", "Set your team name"),
        ("!status", "Show current draft status"),
        ("!undo", "Undo last pick (admin only)"),
        ("!export", "Export data for scoring system"),
        ("!commands", "Show this help message")
    ]
    
    for cmd, desc in commands_list:
        embed.add_field(name=cmd, value=desc, inline=False)
    
    await ctx.send(embed=embed)

# Run the bot
if __name__ == "__main__":
    print("Starting bot...")
    print("Make sure to set your DISCORD_BOT_TOKEN environment variable!")
    
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("ERROR: No DISCORD_BOT_TOKEN found in environment variables!")
        print("Set it with: export DISCORD_BOT_TOKEN='your_token_here'")
    else:
        bot.run(token)
