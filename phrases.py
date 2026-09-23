"""Phrase library for spotting quest instructions in NPC dialogue.

Plain lists, grouped by what they signal. Add a phrase to the right list and
it is live on the next run; no regex knowledge needed. Matching is
case-insensitive and on whole words. A few entries use small regex bits
(`\\w+`, `(a|the)`) where a phrase has variants.

Order of evaluation for each sentence:
  1. NOISE      - if it matches, it is never a task (greetings, small talk).
  2. REQUEST    - "I need you to ...", "could you ...": a task even if phrased as a question.
  3. PHRASES    - task wording anywhere in the sentence.
  4. IMPERATIVE - the sentence opens with an instruction verb (after "Now,", "Then," ...).
Questions that are not REQUESTs are ignored.

DONE_CUES marks the moment an NPC thanks you, so earlier tasks from that NPC are
flagged "likely done".
"""

# ---------------------------------------------------------------- 1. never a task
NOISE = [
    # greetings and small talk
    "well met", "how may i", "how can i help", "yes, what is it", "greetings", "hail,", "hello",
    "it's a pleasure", "pleasure to meet", "good to see you", "nice to meet", "let's cut to",
    "let me introduce", "allow me to introduce", "my name is", "i am (called|known as)",
    "welcome to", "welcome, ", "ah, you must be", "you must be (the|a|an|new|tired|wondering|exhausted|hungry|weary|joking|mistaken|lost|here for)",
    # farewells and pleasantries
    "take care", "safe travels", "farewell", "good luck", "be careful out there", "be safe",
    "may the \\w+ (be with|guide|watch|protect|bless)", "go in peace", "go with \\w+ blessing", "be well",
    "until next time", "see you (around|soon|later)", "off you go", "on your way, then", "go on,? then",
    "go ahead", "run along", "away with you",
    # NPC talking about themself, others, or things: narration, not an instruction to you.
    # (REQUEST is checked first, so "I need you to..." and "We have a task for you" still count.)
    "^(i|we|he|she|they|it|that|this|there|our|my|his|her|their|these|those|everyone|someone|nobody|no one)\\b",
    "^you, too,", "you('re| are) (wanting|looking|hoping|trying|planning|going) to", "in time[.!]$",
    "you can (go|get|head) back to (whatever|your|what|those|the)", "you (can|may) (go|leave|rest) now",
    "i take it you", "i can tell you", "i can't blame you", "i suppose", "i imagine", "i wonder",
    "as you (likely|probably|may|might|no doubt) (know|recall|remember|imagine|expect)",
    "you (may|might) (have )?(heard|noticed|seen|wonder)", "you (are|were|have been) (a )?welcome",
    "you had to make", "you are a welcome addition", "you've come a long way", "you look",
    # figures of speech that contain task verbs
    "take no offense", "take (a|the) (look|seat|moment|breath|hint|liberty|chance|risk)",
    "take all the time", "take (it|things) (easy|slow)", "take my word", "take heart", "take note that",
    "take that as", "take it from me", "make no mistake", "make yourself", "make (a|the) (mess|fuss|scene|point)",
    "make of (it|that|this)", "find (it|that|this) (odd|strange|hard|interesting|amusing|difficult|funny)",
    "find (myself|ourselves|themselves)", "find out (why|how|what) (i|we|they)",
    "give (me|us) a moment", "give (it|that) (no|little) (thought|mind)", "give (me|us) (strength|patience)",
    "look, ", "see, ", "look at (me|you|us|that|this|him|her|them)", "look (here|alive|sharp|lively)",
    "tell me about", "tell the truth", "tell you the truth", "to tell you", "tell you what",
    "speak (quickly|freely|plainly|up|of the devil|for yourself)", "don't mince", "so to speak",
    "go (figure|on|about (your|their)|without saying|so far as)", "here (we|you) go", "there (you|we) go",
    "head (start|on your shoulders|in the clouds|of the)", "keep in mind", "keep (that|this|it) in mind",
    "keep (your|an) (chin|head|spirits|wits|voice|distance)", "keep (up|going|at it|it up)", "mind that you",
    "mind your", "use your (head|brain|common|judg)", "use (a|the) (word|term|phrase)",
    "learn (a|the|your) (lesson|hard way|place)", "read (my|their|his|her) (lips|mind|face)",
    "come (now|come|to think|on)", "come back (some ?time|any ?time|later|whenever|and (see|visit))",
    "return (the|a) (favor|favour|compliment)", "in return for", "bring (a smile|joy|shame|honor|honour|ruin|nothing)",
    "bring(s|ing)? (me|us) (great|much|no|little) (joy|pleasure|comfort|shame)", "meet (your|their|his|her|its) (end|maker|match|fate|doom)",
    "meet (my|our) (eyes?|gaze)", "kill (time|the mood|two birds)", "hunt(ing)? (season|party|lodge)",
    "during your (visit|stay)", "on your (visit|way out|way in)", "show (your|their|his|her) (face|hand|true|worth|colours|colors)",
    "show (me|us) (what|how|that) you", "show (some|a little|more) (respect|courage|initiative)",
    "give (you|him|her|them) (a|the|my|our) (word|blessing|thanks|regards|name)",
    "help (yourself|myself|ourselves)", "can't help (but|it)", "with (the|some) help of",
    "search (me|my heart)", "watch (yourself|your (step|tongue|mouth|back|head))", "watch (it|out)!?$",
    # clearly not instructions
    "do not misunderstand", "don't get me wrong", "no offense", "if you ask me", "if i were you",
    "if you (ask|want) my (opinion|advice)", "i (would|'d) (wager|bet|say|guess|imagine|think)",
    "better acquainted", "under the tutelage", "you'll do fine", "you'll be fine", "you'll get used to",
]

# ---------------------------------------------------------------- 2. a request, even as a question
REQUEST = [
    "(i|we)('d| would|'ll| will|'m|'re| am| are)? ?(need|needs|want|wants|ask|asks|require|expect|would like|'d like|like|beg|implore|urge|trust|count on|rely on) (for )?you to",
    "(i|we)('d| would)? (ask|beg|implore|request) (that )?you",
    "(i|we)('m|'re| am| are) (asking|begging|counting on|relying on|trusting) you",
    "(i|we) (have|'ve got|'ve) (a|another|one more|some|more) (task|job|errand|favor|favour|mission|request|assignment|chore) for you",
    "(could|would|can|will|might) you (please |kindly |perhaps )?(bring|take|fetch|get|find|kill|collect|gather|deliver|return|go|head|speak|talk|tell|show|give|hand|help|escort|carry|retrieve|recover|hunt|clear|check|see|look|search|investigate|report|visit|meet|make|craft|fill|seal|light|read|learn|do|handle|deal|assist|run|pick|grab|track|scout|explore|slay|destroy|defeat|dispose|put)",
    "(would|could) you (be so kind|do me|mind|care to)",
    "if you (could|would|can|might|'d|'ll|will|would be so kind as to) (bring|take|fetch|get|find|kill|collect|gather|deliver|return|go|head|speak|talk|tell|show|give|hand|help|escort|carry|retrieve|recover|hunt|clear|check|see|look|search|investigate|report|visit|meet|make|craft|fill|seal|light|read|learn|handle|deal|assist|run|pick|grab|track|scout|explore|slay|destroy|defeat|dispose|put)",
    "do me a (favor|favour|kindness)", "a (favor|favour) to ask", "(favor|favour) of you",
    "all (i|we) (ask|need|want|require) (is|of you)", "all you (need|have) to do", "what (i|we) (need|want|ask) (is|of you)",
    "here('s| is) what (i|we) need", "the (task|job|mission|errand) is (simple|easy|straightforward|this)",
    "your (task|mission|job|assignment|duty|errand|orders?) (is|are|will be) (to|simple|easy|this)",
    "(this|that|it) (is|will be|shall be) your (first |next |new |only |real |final |last )?(task|mission|job|assignment|duty|errand|test|trial)",
    "you (are|'re) (hereby )?(ordered|instructed|assigned|charged|tasked|commanded|expected|required) to",
    "in (exchange|return|payment)(,| for)? (i|we)('ll| will)",
    "i (challenge|dare) you to",
    # dialect / informal asks: "Ya got some? I love 'em.", "did the cappin' send ya for the tails bounty?"
    "\\b(ya|you|yeh|ye) got (some|any|one|more|a few|em|'em)\\b", "(send|sent) (ya|you|yeh) (for|about) the \\w+ bounty",
    "\\b\\w+s bounty\\b", "\\b(i|we)('ll| will|'d| would)? (take|buy|pay (for|ya|you)|trade (for|ya|you)) (them|those|all|any|every|as many|'em|em|some)\\b",
    "\\b(bring|get|fetch|find) (me|us|ya|yer) (some|any|more|a few)\\b", "\\bgot (any|some) (more )?\\w+s (for|on) (me|ya|you)\\b",
]

# Softer "you should / you must / your next task" wording. Treated like PHRASES: it counts
# unless the sentence is narration, a question, or noise.
OBLIGATION = [
    "your (first|next|new|only|real|final|last|main|current|other|second|third) (task|mission|job|assignment|step|duty|errand|test|trial|challenge|order)",
    "you (are|'re) to ", "you (will|must|need to|have to|should|shall|ought to|'ll need to|'ll have to|'ve got to|'d better|had better) (?!be (tired|wondering|joking|mistaken|new|the|a|an|here))",
    "(be sure|make sure|make certain|see to it|take care|remember|don't forget|do not forget|be certain) (to|that you)",
    "(before|after|once|when) you (do|go|leave|head|return|come back|get there|arrive|reach|finish|are done|'re done|have|'ve)",
    "prove (yourself|your worth|to me|to us|it)", "(show|prove) (me|us) (that )?you (can|are|'re|have)",
    "(earn|win) (my|our|their|his|her) (trust|respect|favor|favour)",
    "if you (want|wish|hope|intend|mean) to (join|earn|prove|help|learn|become|be)",
    "report (back )?to (me|us|him|her|them|\\w+ \\w+)", "(come|return|report) back (to me |here )?(when|once|after|with)",
]

# ---------------------------------------------------------------- 3. task wording anywhere
PHRASES = [
    # fetch / deliver
    "bring (me|us|it|them|this|that|back|the|him|her|any|some|a|an|one|two|three|four|five|six|seven|eight|nine|ten|\\d+)",
    "return (it|them|the|this|that|to|with|here|when|once|and)", "deliver", "hand (it|them|this|that|the|him|her) (over|to)",
    "give (it|them|this|that|the|him|her) to", "take (this|these|that|the|it|them|him|her|your) .* (to|back|over|down|up|into|across)",
    "show (this|these|that|the|it|him|her|them|your) .* to", "present (this|these|that|the|it|your) .* to",
    "carry (this|these|that|the|it|them) .* to", "escort (him|her|them|the|this|my|our)", "(accompany|guide|lead) (him|her|them|the|my|our) (to|back|through|out)",
    "fetch", "retrieve", "recover", "obtain", "acquire", "procure", "secure (the|a|an|some|\\d+)", "get (me|us) (the|a|an|some|\\d+)",
    "pick up (the|a|an|some|\\d+)", "grab (the|a|an|some|\\d+|me|us)", "collect", "gather", "harvest", "forage", "mine (the|some|\\d+)",
    "fill (the|it|this|a|that|my|your|up)", "seal (it|the|this|that)", "wrap (it|them|the) up", "tie (it|them|these|those) (to|together|around)",
    "(stuff|pack|load) (it|the|this|that) (with|full)", "(six|five|four|three|two|eight|ten|a dozen|\\d+) (of (their|its|the) )?\\w+s? (and|then|from|for)",
    # kill / clear
    "kill", "slay", "slaughter", "cull", "exterminate", "eliminate", "eradicate", "destroy", "defeat", "vanquish", "dispatch (the|a|an|them|those|\\d+)",
    "put (down|an end to|a stop to)", "drive (off|out|away|back)", "clear (out|the|them|those|a path|the way)", "cleanse", "purge", "rid (the|this|us|me|them) of",
    "hunt (down|the|some|a|\\d+)", "track down", "thin (out )?(their|the|its)", "deal with (the|those|them|that)", "take care of (the|those|them|that|it)",
    "(bring|take) (them|him|her|it) down", "engage (the|them|those|any)", "fight (off|back|the|them)", "hold (them|the line|the)",
    "(defend|protect|guard|watch over) (the|this|my|our|him|her|them)", "(free|rescue|save|liberate) (the|him|her|them|my|our)",
    "(capture|catch|trap|snare|net) (the|a|an|some|\\d+)", "(tame|bond with|befriend) (a|an|the|one)",
    # find / go
    "investigate", "find (evidence|a|an|the|some|any|out|him|her|them|where|what|who|why|how|my|our|his|its)", "locate", "seek (out|the|a|an|him|her|them)",
    "search (for|the|every|each|his|her|their|its|through|among)", "look for", "look (into|around|through|under|behind|inside)",
    "scout (the|out|ahead|for)", "explore", "(inspect|examine|check on|check out|survey) (the|a|an|his|her|their|its)", "keep an eye (out|on)", "keep watch",
    "make note of", "take note of", "(observe|monitor) (the|them|him|her|any)", "go (to|see|find|speak|talk|meet|and|back|down|up|out|into|through|there|now|west|east|north|south|inside|outside)",
    "head (to|out|over|back|into|through|down|up|west|east|north|south|toward|towards|for|there|straight)", "(make|find) your way (to|back|through|down|up|into)",
    "(travel|journey|venture|proceed|continue|walk|ride|sail|climb|descend) (to|toward|towards|into|through|down|up|out|back|on|west|east|north|south)",
    "visit (him|her|them|the|old|my|our|\\w+ \\w+ (at|in|by|near))", "go (and )?see (him|her|them|old|my|our|\\w+ \\w+)",
    "meet (with |up with )?(him|her|them|me|us|the|my|our|\\w+ (at|in|by|near|outside|inside))",
    "(follow|trail|shadow) (the|him|her|them|it|this|that|my|these)", "(wait|stay|remain|stand) (for|by|near|at|here|there|until|with)",
    "(return|come|go|get|report) back", "come (find|see|to|back to|talk to|speak with) me", "return to me", "back to me",
    # speak
    "speak (to|with)", "talk (to|with)", "tell (him|her|them|me (when|once|you|if|what|about your)|\\w+ (that|about|i|we|to))",
    "(ask|inform|notify|alert|warn|advise|consult|question|interrogate) (him|her|them|the|my|our|\\w+ \\w+)", "(let|inform) (him|her|them|\\w+) know",
    "(pass|relay|carry|send) (this|the|my|our|a) (message|word|news|warning|note|letter)", "(send|give) (him|her|them|\\w+) my (regards|thanks|word)",
    "(seek|get|ask for) (his|her|their) (help|aid|counsel|advice|blessing|permission|approval)",
    # make / use
    "(craft|forge|brew|cook|bake|sew|stitch|tan|smith|assemble|build|construct|fashion|carve|weave|make|prepare) (me|us|a|an|the|some|\\d+|it|them)",
    "(repair|fix|mend|restore|rebuild|reforge) (the|it|this|that|my|our|his|her)", "(light|extinguish|snuff|ignite|kindle) (the|a|an|it|this|these|each|every)",
    "(activate|trigger|pull|push|turn|ring|strike|sound) (the|a|an|it|this|that|each|every)", "(place|plant|set|put|position|hang|bury|hide) (it|this|these|them|the|a|an) (in|on|at|by|near|under|inside|behind)",
    "(open|unlock|close|lock|bar|seal) (the|a|an|it|this|that|every|each)", "(read|study|learn|memorize|memorise|recite) (the|this|these|your|from|it|them)",
    "(use|wield|wear|equip|don|carry|drink|eat|consume|apply|smear|sprinkle|pour) (the|this|these|it|them|your|a|an|some)", "(practice|practise|train|drill|spar) (with|until|your|the|on)",
    "(dig|excavate) (up|out|for|at|under|near|the)", "(burn|torch|set fire to|sacrifice|offer up|offer) (the|it|them|this|that|these|those|a|an)",
    "(sign|mark|stamp|inscribe|write) (the|your|this|it|a|an)", "(feed|heal|treat|tend|cure|nurse|water|groom) (the|a|an|it|them|him|her|my|our|your|these|those)",
    "(pay|purchase|buy|sell|trade|barter|bargain) (for|the|a|an|some|it|them|him|her|with)", "(earn|raise|save up|scrape together) (enough|the|some|\\d+)",
    "(complete|finish|accomplish|perform|undertake|carry out|fulfil|fulfill|see through) (the|this|that|it|your|my|our|his|her|their|each|every|all)",
    "(help|assist|aid) (him|her|them|me|us|the|my|our|\\w+ \\w+ (with|in|by))",
    # completion conditions
    "once (that's|that is|you've|you have|you're|you are|it's|it is|they're|they are|the|this|all)", "when (you're|you are|that's|that is|it's|it is|you've|you have|all|the|this) (done|finished|complete|ready|over|through|dealt)",
    "(and |then )?(return|come back|report back|bring (it|them|everything|the) back)", "(as|so) (soon|quickly|fast) as (you|possible)",
    "before (nightfall|dawn|dusk|sunrise|sunset|the|it's too late|they)", "(and|then) (i|we)('ll| will|'d| would) (reward|pay|give|tell|show|teach|help|let|see|talk|speak|consider|know)",
]

# ---------------------------------------------------------------- 4. sentence opens with an instruction verb
IMPERATIVE_VERBS = [
    "bring", "take", "carry", "deliver", "return", "fetch", "retrieve", "recover", "collect", "gather", "harvest",
    "mine", "fish", "forage", "hunt", "kill", "slay", "cull", "exterminate", "eliminate", "eradicate", "destroy",
    "defeat", "vanquish", "dispatch", "put down", "drive", "clear", "cleanse", "purge", "rid", "find", "locate",
    "seek", "search", "look for", "scout", "explore", "investigate", "inspect", "examine", "check", "survey",
    "visit", "go", "head", "travel", "journey", "venture", "make your way", "proceed", "continue", "report",
    "speak", "talk", "tell", "ask", "inform", "notify", "warn", "consult", "see", "meet", "escort", "guide",
    "accompany", "protect", "defend", "guard", "watch over", "keep watch", "keep an eye", "show", "present",
    "give", "hand", "offer", "pay", "purchase", "buy", "sell", "trade", "craft", "forge", "brew", "cook", "bake",
    "sew", "tan", "smith", "assemble", "build", "construct", "repair", "fix", "mend", "light", "extinguish",
    "activate", "place", "plant", "bury", "dig", "open", "unlock", "read", "study", "learn", "practice",
    "practise", "train", "use", "wear", "equip", "drink", "eat", "consume", "fill", "seal", "wrap", "tie", "bind",
    "mark", "sign", "follow", "track", "trail", "wait", "stay", "remain", "keep", "hold", "dispose", "burn",
    "sacrifice", "offer up", "pray", "kneel", "get", "grab", "pick up", "acquire", "obtain", "secure", "earn",
    "prove", "demonstrate", "complete", "finish", "accomplish", "perform", "undertake", "help", "assist", "aid",
    "save", "rescue", "free", "release", "capture", "catch", "trap", "tame", "bond", "feed", "heal", "treat",
    "tend", "cure", "make sure", "be sure", "see to it", "remember to", "don't forget to", "do not forget to",
    "come back", "come find", "come see", "send", "spread", "deal with", "take care of", "put an end",
    "thin out", "drive off", "drive out", "clear out", "track down", "hunt down", "seek out", "look into",
]

# Words that may precede the imperative verb at the start of a sentence.
LEAD_INS = [
    "now", "then", "first", "firstly", "second", "next", "also", "afterward", "afterwards", "after that",
    "but", "and", "so", "please", "oh, and", "one more thing", "lastly", "finally", "meanwhile", "in the meantime",
    "if you would", "if you please", "if you can", "if you're able", "if you are able", "when you can", "when you have a moment",
    "for now", "for the moment", "as for you", "in that case", "very well", "good", "excellent", "right",
    "but before [^,]+", "once [^,]+", "when [^,]+", "after [^,]+", "before [^,]+", "if [^,]+", "should you [^,]+", "while [^,]+",
]

# ---------------------------------------------------------------- 5. NPC thanks you: earlier tasks are likely done
DONE_CUES = [
    "thank you for", "thanks for (your|the|that|this|bringing|helping|coming|doing|finding|dealing|taking|returning)",
    "(you have|you've|i have|we have) my (thanks|gratitude)", "my (sincere |deepest |heartfelt )?(thanks|gratitude)", "many thanks",
    "excellent work", "well done", "good work", "fine work", "nicely done", "splendid", "impressive", "well, well",
    "you('ve| have) (done|returned|brought|proven|found|dealt|completed|finished|earned|succeeded|managed|delivered|recovered|retrieved)",
    "you did it", "this is excellent", "just what (i|we) needed", "exactly what (i|we) (needed|asked)", "(that's|that is|these are|this is) (perfect|precisely|exactly)",
    "looks through the bag", "nods appreciatively", "good, you('ve| have)", "done well to", "you have done well",
    "accept this (gift|reward|token|payment|coin|purse)", "(here|this) is your (reward|payment|share|due)", "in return", "as (promised|agreed|payment|a reward|thanks|a token)",
    "for your (assistance|help|efforts?|service|trouble|work|kindness|bravery|courage|deed)", "a (small |little |modest )?(token|reward|gift|something) (of|for)",
    "you('ve| have) earned", "(take|keep) (this|these|it) (as|for your)", "(consider|call) (it|us|this) (even|square|settled)",
    # emote lines: the NPC takes or inspects what you brought
    "^(takes|accepts|receives|grabs|snatches|collects|pockets) (the|your|a|an|each|all|both|them|it)",
    "^(reads|reads over|skims|scans|examines|inspects|studies|looks over|unfurls|unrolls) (the|your|it|over the)",
    "^(looks|peers|rummages|digs|sifts) (through|into|inside) (the|your|it)", "counting (out )?(the|your|each)",
    "(weighs|hefts|sniffs|tastes|bites) (the|your|it|each)", "from your hands?", "sets? (it|them|the \\w+) aside",
]
