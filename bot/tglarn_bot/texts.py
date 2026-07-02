"""User-facing Telegram texts.

All in-game and menu text must stay in English.
"""

MAIN_MENU_TEXT = """<b>TGLarn</b>
Choose an action."""

ABOUT_TEXT = """<b>About</b>
Your daughter is dying from a strange disease, and ordinary remedies have failed.

Rumors point to the Caverns of Larn: a dangerous underground world once used by
the magician Polinneaus for the creation of magic. The caverns may hold treasure,
spells, and the one thing that can save her.

You are an explorer with little time, limited resources, and one job: survive the
dungeon long enough to find a cure."""

INTRO_TEXT = """<b>Before the Caverns</b>
Your child is dying from dianthroritis. The healers cannot stop it.

There is one last hope: descend into the Caverns of Larn, find the legendary
Potion of Cure Dianthroritis, and bring it home before time runs out.

The town is quiet. The dungeon entrance is nearby. First, choose who will enter."""

CHARACTER_CLASS_TEXT = """<b>Create Character</b>
Choose your class. Each class starts with different stats, gear, and spell access."""

CHARACTER_CLASS_GUIDE_TEXT = """<b>Class Guide</b>
New players: Geek, Dwarf, or Rogue are the safest starts. Rambo is a challenge class.

<b>Ogre</b> - HP 16, brute survivor.
Magic missile. Starts with 2 random potions.

<b>Wizard</b> - HP 8, fragile caster.
Magic missile and charm. Starts with treasure finding and scrolls.

<b>Klingon</b> - HP 14, armored fighter.
Sonic spear. Starts with studded leather and a potion.

<b>Elf</b> - HP 8, defensive caster.
Protection spell. Starts with leather and a scroll, but no weapon.

<b>Rogue</b> - HP 12, agile scout.
Magic missile. Starts with leather, dagger, and stealth.

<b>Geek</b> - HP 10, balanced starter.
Protection and magic missile. Starts with leather and dagger.

<b>Dwarf</b> - HP 12, tough melee.
Protection spell. Starts with a spear.

<b>Rambo</b> - HP 1, challenge mode.
No spells. Starts with the lance of death."""

CHARACTER_GENDER_TEXT = """<b>Create Character</b>
Class: <b>{character_class}</b>

Choose your character gender."""

CHARACTER_CREATED_TEXT = """<b>Character Created</b>
{gender} {character_class}

The run begins."""

RULES_MENU_TEXT = """<b>Rules</b>
Choose which part of the game reference you want to read."""

CONTROLS_TEXT = """<b>Controls</b>
TGLarn uses Telegram buttons for normal play. Text aliases remain available for
players who prefer typing commands directly.

<b>Movement</b>
<pre>NW / N / NE
 W / Inspect / E
SW / S / SE</pre>

<b>Combat and Magic</b>
<pre>Move into a monster  melee attack
Spell                 open spell actions
Known Spells          list learned spells
Cast Spell            cast a spell</pre>

<b>Context Actions</b>
Context buttons appear only when the current map state supports them.

<pre>Descend          go down stairs
Close Door       close a nearby open door
Identify Trap    identify a visible adjacent trap</pre>

<b>Game Menu</b>
<pre>Inventory      show inventory
Pack Weight    show pack weight
Wield Weapon   wield a weapon
Wear Armor     wear armor
Take Off       take off shield or armor
Drop Item      drop an item
Read Scroll    read a scroll
Quaff Potion   quaff a potion
Eat            eat something
Teleport       teleport yourself, once you know how</pre>"""

GAME_MECHANICS_TEXT = """<b>Game Mechanics</b>
TGLarn is based on ReLarn/Larn, an old-school turn-based roguelike.

Every direct chat with the bot is one private player session.
Progress is saved automatically after actions.
There is no manual save/load flow in the Telegram version.

Core loop:
- explore the dungeon one turn at a time;
- use descend / go down / > when standing on stairs to go deeper;
- moving into a monster performs a melee attack;
- spells, scrolls, potions, equipment, traps, doors, stairs, and contextual
  objects create most of the tactical choices;
- monsters act as turns pass;
- better gear, useful magic, and careful resource management keep you alive;
- death or Restart Game starts a fresh run.

Use Legend from the main menu when you need to decode map symbols."""

LEGEND_TEXT = """<b>Legend</b>
ReLarn reuses letters. In the original terminal UI color helped; in Telegram
plain text it does not. If a symbol is ambiguous, step on it or use Inspect:
the log and context buttons tell you what it is.

Examples: D can be a closed door or a dragon. C can be a chest or a centaur.

<b>Map Basics</b>
<pre>@  you
.  known floor
space  unexplored fog or hidden trap
#  wall
D  closed door
O  open door
%  stairs up/down
^  traps or elevators
&gt;  stairs down
X  dungeon exit
E  dungeon entrance</pre>

<b>Town and Places</b>
<pre>H  your home
@  Dealer McDope's Pad
+  University of Larn
=  DND store
$  Bank of Larn
S  Larn trading post
L  Larn Revenue Service
V  volcanic shaft
A  altar
T/t  throne / dead throne
F/f  fountain / dead fountain
P  pit
&amp;  statue</pre>

<b>Items</b>
<pre>*  gold
!  potion
?  scroll
(  weapon
)  sword, axe, or special weapon
[  armor or shield
]  heavy armor
|  ring
{  belt
/  wand or staff
:  drug
'  diploma
.  charm, amulet, lamp, or small item
&lt;  gem
o  orb
~  Eye of Larn
B  book
C  chest
c  fortune cookie
s  sphere of annihilation</pre>

<b>Monsters</b>
Uppercase and lowercase are different.
<pre>0  God of Hellfire
1-7  demon lord types I-VII
9  demon prince
A  giant ant
C  centaur
D  dragons
E  floating eye
F  violet fungus
G  gnome
H  hobgoblin
I  invisible stalker
J  jackal
K  kobold
L  leprechaun
M  mimic
N  nymph
O  orc
P  purple worm
Q  quasit
R  rust monster
S  snake
T  troll
U  umber hulk
V  vampire
W  wraith
X  xorn
Y  yeti
Z  zombie
a  assassin bug
b  bitbug
c  giant centipede
d  white dragon
e  elf
f  forvalaka
g  gelatinous cube
h  hell hound
i  ice lizard
j  jaculus
k  gnome king
l  lemming / lama nobe
m  metamorph
n  spirit naga
o  osequip
p  poltergeist
q  disenchantress
r  rothe
s  shambling mound
t  troglodyte
u  green urchin
v  vortex
w  water lord
x  xvart
y  yellow mold
z  zill</pre>"""

RESTART_CONFIRM_TEXT = """<b>Restart game?</b>
Are you sure? Current progress will be lost!"""

RESTARTED_TEXT = """<b>Game restarted.</b>
A fresh run is ready."""

MAP_VIEW_TEXT = """<b>Display size</b>
Choose the map viewport size used in game messages.

Medium is kept for smaller or older phones. Wide is intended for modern phones.
Max Size uses the widest map that fits without line wrapping."""

MAP_VIEW_UPDATED_TEXT = """<b>Display size updated.</b>
Current size: <b>{view}</b>."""

SPELL_MENU_TEXT = """<b>Spell</b>
Choose a spell action."""

GAME_MENU_TEXT = """<b>Game Menu</b>
Choose an inventory, equipment, item, or travel action."""

REPOSITORY_TEXT = """<b>Repository</b>
Project source code will be available here:"""
