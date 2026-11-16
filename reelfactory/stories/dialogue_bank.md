# Dialogue story bank (the cartoon format)

Every spoken line is said by one character, in the first person, in that character's own voice (voices.json).
No narration: no "X बोला", no "X ने कहा". The narrator only reads the end card.

NEW FORMAT (story-upgrade): a story that carries a `card:` line is also judged by the cold-open, plot-vs-dialogue, typo, card and series rules (scripts/story_rules.py).
Extra field lines, after `hook:`: `card:` = the 3 to 5 word on-screen hook (Hindi only, at most 30 characters, no emoji, no digits, shown in the first 1.5 s),
`series:` + `ep:` = a series episode (name and number; must both be set; the last spoken line must end with ?).
Cold open: the FIRST spoken line is the conflict or the payoff, never a polite question or a greeting.

Format: `## <English title> | <Hindi title>`, then `plot:`, `ending:` (2 to 5 Hindi words, read by the narrator just
before the DASHX line on the end card) and exactly four scene rows:

    - template | who_a | who_b | board | speaker: line // speaker: line

* 1 or 2 lines per scene; with 2 lines the speakers are two different characters (A asks, B answers; B's answer is the joke).
* The speakers must be on stage in that scene (see below). The LAST line of the last scene is the punchline.
* A line is at most 14 words (aim for 4 to 7: the whole reel must fit in 25 seconds). Devanagari only, no digits.
* Bruno never speaks words: his line is a bark, e.g. `bruno: भौं भौं!`.
* Who is on stage: face-off = who_a, who_b; run-up = bowler who_a, batter who_b; shot = batter who_a, watcher who_b;
  catch = catcher who_a (dadaji, aunty, coach or pintu), watcher who_b and the optional second watcher in `board`.
* `board` is the pop-up word on the scoreboard (face-off only, empty for the other templates): ONE short Hindi word of up to 8 characters, e.g. आउच, सीटी. No English.

## Fake Cramp Talk | मोच का बहाना
plot: Sachin pretends to have a cramp so he does not have to bowl, forgets it when he hits a six and runs, and Coach asks where the cramp went.
ending: मोच अपने आप ठीक!
hook: सचिन की मोच सच्ची थी या बहाना? 😅
- face-off | sachin | coach | आउच | sachin: कोच जी, मेरे पैर में मोच है! // coach: ठीक है, आज गेंद मत डालना।
- run-up | meena | sachin | | meena: तो आज मैं गेंद डालूँगी!
- shot | sachin | meena | | sachin: छक्का! भागो भागो भागो! // meena: सचिन, तुम तो दौड़ रहे हो!
- catch | coach | sachin | pintu | coach: दौड़ते हुए तेरी मोच कहाँ गई? // sachin: वो तो रास्ते में गिर गई!

## Two Whistles Talk | सीटी पर झगड़ा
plot: Pintu and Coach both claim the same whistle, Surya cannot tell whose whistle to obey, and Aunty ends the argument by taking the whistle herself.
ending: आंटी बनीं अंपायर!
hook: एक सीटी, दो दावेदार, फ़ैसला किसका? 🤔
- face-off | pintu | coach | सीटी | pintu: कोच जी, यह मेरी सीटी है! // coach: नहीं पिंटू, यह मेरी सीटी है!
- run-up | golu | surya | | golu: भैया, गेंद डालूँ क्या? // surya: सीटी बजे तो डालना!
- shot | surya | golu | | surya: दो सीटी? मैं रुकूँ या खेलूँ?
- catch | aunty | pintu | coach | pintu: आंटी, मेरी सीटी वापस दो! // aunty: अब सीटी सिर्फ़ मैं बजाऊँगी!

## Sneeze Talk | छींक वाला कैच
plot: Dadaji has a dusty nose, Surya hits a six straight at him, Dadaji sneezes and catches the ball by reflex, and Surya calls him a hero.
ending: छींक का आशीर्वाद मिला!
hook: दादाजी की छींक ने क्या कमाल कर दिया? 🤧
- face-off | surya | dadaji | आछूँ | surya: दादाजी, आपको ज़ुकाम है क्या? // dadaji: नहीं बेटा, बस धूल है।
- run-up | sachin | surya | | sachin: सूर्या, मैं गेंद डालूँ? // surya: डाल, पर आज ज़रा संभलकर!
- shot | surya | dadaji | | surya: ये लो छक्का! // dadaji: आ, आ, आछूँ!
- catch | dadaji | surya | sachin | dadaji: लो, छींकते-छींकते पकड़ लिया! // surya: दादाजी, आप तो छींक में भी हीरो हो!

## Big Shoes Talk | बड़े जूते, छोटा गोलू
plot: Golu borrows Coach's huge shoes and cannot keep up with them, Meena hits a six, and Coach catches it and wants his shoes back, which is fine with Golu.
ending: जूतों में गोलू लड़खड़ाया!
hook: गोलू ने कोच से उनके जूते क्यों माँगे? 👟
- face-off | golu | coach | जूते | golu: कोच जी, आपके जूते दे दो! // coach: बहुत बड़े हैं तेरे लिए!
- run-up | golu | meena | | meena: गोलू, तू भाग क्यों नहीं रहा? // golu: जूते आगे हैं, मैं पीछे!
- shot | meena | golu | | meena: ये रहा मेरा छक्का!
- catch | coach | golu | meena | coach: गोलू, जूते मेरे, कैच भी मेरा! // golu: अब मुझे आपके जूते नहीं चाहिए!

## Digging Bruno Talk | ब्रूनो की खुदाई
plot: Bruno digs up the pitch, Sachin's foot gets stuck in the hole, Surya hits a six first and helps later, and Aunty explains that Bruno buried a bone.
ending: पिच बना खदान!
hook: ब्रूनो पूरी पिच क्यों खोद रहा है? 🐶
- face-off | surya | bruno | खुदाई | surya: ब्रूनो, पिच मत खोदो! // bruno: भौं भौं!
- run-up | sachin | surya | | sachin: सूर्या, मेरा पैर अटक गया!
- shot | surya | sachin | | surya: पहले ये लो छक्का! // sachin: अरे, पहले मुझे निकालो!
- catch | aunty | bruno | sachin | bruno: भौं भौं! // aunty: अच्छा, हड्डी यहाँ दबाई थी!

# Converted from the narrated bank (30 stories). Same plots, now spoken by the characters. Checked by scripts/check_dialogue_bank.py

## Umpire's Tea | पिंटू की चाय
plot: Umpire Pintu stops the game for tea, Surya bowls anyway, Sachin's shot heads for Pintu's cup, and Aunty saves both the cup and the ball.
ending: आंटी के हाथ में जादू!
hook: अंपायर साहब की चाय पर किसकी नज़र थी? 🍵
- face-off | pintu | surya | चाय | pintu: रुको! चाय का ब्रेक हो गया! // surya: ब्रेक बाद में, पहले गेंद!
- shot | sachin | pintu | | sachin: ये गया शॉट! // pintu: अरे, मेरी चाय का कप!
- catch | aunty | pintu | surya | aunty: पकड़ लिया! कप भी, गेंद भी!
- face-off | pintu | aunty | शुक्रिया | pintu: आंटी, आप तो जादूगर हो! // aunty: जादू छोड़ो, अब चाय मैं पिऊँगी!

## Pickle Jars | अचार के मर्तबान
plot: Aunty dries pickle jars on the wall, Surya promises to bowl straight, Sachin's shot flies toward the jars, and Aunty catches the ball and a jar together.
ending: अचार भी सुरक्षित, गेंद भी!
hook: आंटी का अचार बचेगा या गेंद भारी पड़ेगी? 😬
- face-off | aunty | surya | अचार | aunty: ख़बरदार! मेरा अचार मत गिराना! // surya: चिंता मत करो आंटी, सीधी डालूँगा!
- run-up | surya | sachin | | sachin: सूर्या, टेढ़ी डाली तो अचार गया! // surya: मेरी गेंद और टेढ़ी? नामुमकिन!
- shot | sachin | surya | | sachin: ये लो शॉट! // surya: अरे, मर्तबान की तरफ़ गया!
- catch | aunty | sachin | surya | aunty: एक हाथ में गेंद, दूसरे में अचार! // sachin: आंटी, आप तो कमाल हो!

## Mango Catch | आम का कैच
plot: Meena's ball gets stuck in a mango tree, Coach shakes the branch, and Dadaji catches a falling mango instead of the ball.
ending: आम मीठा, गेंद गुम!
hook: गेंद अटकी आम के पेड़ में, फिर गिरा क्या? 🥭
- shot | meena | coach | | meena: ओह! गेंद आम के पेड़ में अटक गई!
- face-off | coach | meena | हिलाओ | coach: हटो, मैं पेड़ हिलाता हूँ! // meena: कोच जी, ज़ोर से हिलाइए!
- catch | dadaji | coach | meena | dadaji: ये लो कैच! अरे, यह तो आम है!
- face-off | meena | dadaji | गेंद | meena: दादाजी, मेरी गेंद कहाँ गई? // dadaji: बेटी, आम खाओ, गेंद भूल जाओ!

## Bruno Steals | ब्रूनो की चोरी
plot: Surya tells Bruno to drop the ball, Sachin's shot sends Bruno running after it, and Bruno tosses the ball straight into Dadaji's hands.
ending: ब्रूनो की शरारत रंग लाई!
hook: गेंद लेकर भागा ब्रूनो, अब कौन रोकेगा? 🐕
- face-off | surya | bruno | छोड़ो | surya: ब्रूनो, मेरी गेंद वापस दो! // bruno: भौं भौं!
- shot | surya | bruno | | surya: रुक जा चोर, मैं बल्ला उठाता हूँ! // bruno: भौं भौं भौं!
- catch | dadaji | sachin | bruno | dadaji: अरे वाह, गेंद सीधी मेरे हाथ में!
- face-off | sachin | surya | इनाम | sachin: देखा, चोर ने ख़ुद गेंद लौटा दी! // surya: तो इस चोर को इनाम में हड्डी दो!

## Hat-trick Talk | छक्कों की हैट्रिक
plot: Surya boasts that he will hit three sixes in a row, his first shot just rolls on the ground, and Dadaji asks him to score one run first.
ending: बातें बड़ी, रन छोटे!
hook: तीन छक्कों का वादा, कितने निकले? 🏏
- face-off | surya | sachin | छक्के | surya: आज लगातार तीन छक्के मारूँगा! // sachin: पहले एक तो मारकर दिखा!
- run-up | sachin | surya | | sachin: ले, पहली गेंद आ रही है! // surya: देखता जा, आसमान में जाएगी!
- shot | surya | sachin | | surya: लो, उड़ा दिया छक्का! // sachin: वो तो ज़मीन पर लुढ़क रही है!
- face-off | dadaji | surya | रन | dadaji: बेटा, पहले एक रन तो बना ले! // surya: ठीक है, अगली बार एक रन पक्का!

## Meena's Rule | मीना का नियम
plot: Meena makes a no-boasting rule, then hits a six and boasts herself, and Pintu blows the whistle on her.
ending: नियम बनाने वाली ही फँसी!
hook: नियम बनाने वाली ख़ुद फँस जाए तो? 😜
- face-off | meena | surya | नियम | meena: आज से डींग मारना मना है! // surya: ठीक है, मैं चुप रहूँगा।
- run-up | surya | meena | | surya: चुपचाप गेंद डाल रहा हूँ! // meena: शाबाश, अब देखो मेरा शॉट!
- shot | meena | pintu | | meena: छक्का! मैं तो चैंपियन हूँ! // pintu: पीप पीप! यह तो डींग है!
- face-off | pintu | meena | सीटी | pintu: मीना, तुम्हारा नियम, तुम्हीं आउट! // meena: ठीक है, अगला नियम, अंपायर चुप!

## Power Cut | बत्ती गुल
plot: The lights go out during the game, the boys play by guessing, and Dadaji catches the ball with a torch in his lap.
ending: बत्ती गई, खेल नहीं!
hook: बत्ती गुल, पर खेल चालू! गेंद कहाँ गई? 🔦
- face-off | sachin | surya | अँधेरा | sachin: अरे! बत्ती चली गई! // surya: कोई बात नहीं, खेल जारी रहेगा!
- run-up | surya | sachin | | surya: अंदाज़े से गेंद डाल रहा हूँ! // sachin: मैं आवाज़ सुनकर खेलूँगा!
- shot | sachin | surya | | sachin: चटाक! लगा या नहीं? // surya: पता नहीं, कहीं गिरी होगी!
- catch | dadaji | surya | sachin | dadaji: गेंद मेरी गोद में आ गिरी! // surya: दादाजी, अँधेरे में भी निशाना पक्का!

## Dadaji's Newspaper | अख़बार वाले दादाजी
plot: Surya tells everyone to be quiet because Dadaji is reading, Golu's little shot flies into the newspaper, and Dadaji catches it from behind the paper.
ending: अख़बार में आज: गेंद!
hook: अख़बार पढ़ते दादाजी के पास गेंद आई तो? 📰
- face-off | dadaji | surya | श्श | dadaji: श्श! अख़बार पढ़ रहा हूँ। // surya: सॉरी दादाजी, हम धीरे खेलेंगे!
- shot | golu | dadaji | | golu: ये मेरा छोटा सा शॉट! // dadaji: अरे, मेरे अख़बार में घुस गया!
- catch | dadaji | golu | surya | dadaji: पकड़ ली गेंद, अख़बार के पीछे से!
- face-off | golu | dadaji | ख़बर | golu: दादाजी, आपने कैच कैसे पकड़ा? // dadaji: बेटा, आज की ताज़ा ख़बर, मैं जाग रहा हूँ!

## Sleepy Six | नींद वाला छक्का
plot: Surya asks Sachin not to fall asleep, Sachin yawns as the ball arrives, and his sleepy swing becomes a six that Aunty catches from her window.
ending: सोते-सोते भी छक्का!
hook: नींद में बल्ला घुमाया तो क्या होगा? 😴
- face-off | surya | sachin | जागो | surya: सचिन, आज सो मत जाना! // sachin: नहीं नहीं, मैं पूरा जाग रहा हूँ।
- shot | sachin | surya | | sachin: आ, आ, आऽ, जम्हाई! // surya: अरे, बल्ला घूम गया और छक्का!
- catch | aunty | sachin | surya | aunty: खिड़की से ही कैच ले लिया!
- face-off | sachin | aunty | सपना | sachin: आंटी, मैंने छक्का मारा या सपना देखा? // aunty: सपने में भी छक्का, शाबाश!

## School Bell | स्कूल की घंटी
plot: The school bell rings, Coach allows one last ball, Meena hits it with her school bag on, and Coach catches it before everyone runs home.
ending: कल फिर, पर होमवर्क पहले!
hook: घंटी बजी, पर आख़िरी गेंद अभी बाक़ी है! 🔔
- face-off | coach | golu | घंटी | coach: घंटी बज गई, आख़िरी गेंद खेलो! // golu: कोच जी, बस्ता भारी है!
- run-up | golu | meena | | golu: ये ले आख़िरी गेंद! // meena: बस्ते के साथ ही मारूँगी!
- catch | coach | golu | meena | coach: पकड़ लिया! अब सब घर भागो!
- face-off | golu | meena | होमवर्क | golu: मीना, होमवर्क किसने किया है? // meena: कल फिर खेलेंगे, कल कर लेंगे!

## Laundry Line | कपड़ों की रस्सी
plot: Surya's shot lands in Aunty's washing, Aunty asks how the ball got on her sheet, Surya hides, and Aunty catches the ball through the sheet.
ending: सूर्या चादर में ग़ायब!
hook: आंटी की चादर पर गेंद, सूर्या कहाँ छुपा? 👀
- shot | surya | aunty | | surya: छक्का! अरे, गेंद आंटी की चादर में! // aunty: यह किसकी गेंद है मेरी चादर पर?
- face-off | aunty | surya | चादर | aunty: बताओ, मेरी चादर पर गेंद कैसे? // surya: आंटी, हवा से आ गई होगी!
- catch | aunty | surya | sachin | aunty: हवा से? लो, चादर से ही पकड़ ली!
- face-off | sachin | surya | कहाँ | sachin: सूर्या कहाँ गया? // surya: मैं चादर में हूँ, मुझे मत ढूँढो!

## Chair Fight | कुर्सी की लड़ाई
plot: Dadaji tells Coach the chair is his, Sachin's shot flies at the chair, and Dadaji catches it without leaving his seat.
ending: कुर्सी का राजा दादाजी!
hook: कुर्सी किसकी, दादाजी की या कोच की? 😤
- face-off | dadaji | coach | कुर्सी | dadaji: यह मेरी कुर्सी है, कोच! // coach: दादाजी, आज मेरी बारी है!
- shot | sachin | coach | | sachin: लो, मेरा शॉट कुर्सी की ओर! // coach: सँभलो, सीधा कुर्सी पर जा रहा है!
- catch | dadaji | coach | sachin | dadaji: मैंने कुर्सी से हिले बिना पकड़ लिया!
- face-off | coach | dadaji | हार | coach: ठीक है दादाजी, कुर्सी आपकी! // dadaji: और अगला कैच भी मेरा!

## Golu's Counting | गोलू की गिनती
plot: Golu counts the runs in his own way, Pintu corrects him, and Golu still calls Coach's catch eleven out.
ending: गोलू की गिनती गोलू जाने!
hook: गोलू की गिनती कभी सही निकली है? 🔢
- face-off | golu | pintu | गिनती | golu: एक, दो, पाँच, दस रन! // pintu: गोलू, यह कैसी गिनती है?
- shot | meena | golu | | meena: मैंने बस एक रन लिया! // golu: मैं तो दस गिनूँगा!
- catch | coach | golu | pintu | coach: लो, कैच पकड़ लिया!
- face-off | golu | pintu | ग्यारह | golu: ग्यारह आउट! // pintu: गोलू, आउट एक ही बार होता है!

## Aunty Keeps The Ball | आंटी की ज़ब्ती
plot: Surya's shot lands on Aunty's roof and she says the ball is hers now, the boys beg for a chance, and she returns it with an invitation for tea.
ending: गेंद मिली, चाय भी!
hook: गेंद गई आंटी की छत पर, अब शर्त क्या? 🏠
- shot | surya | aunty | | surya: अरे! गेंद आंटी की छत पर गई! // aunty: यह गेंद अब मेरी है!
- face-off | surya | aunty | ज़ब्त | surya: आंटी, एक मौक़ा दे दो! // aunty: पहले माफ़ी माँगो!
- catch | aunty | surya | sachin | aunty: ठीक है, लो गेंद, पर कल चाय मेरे घर!
- face-off | surya | sachin | चाय | surya: सचिन, गेंद भी मिली, चाय भी! // sachin: ऐसी ज़ब्ती तो रोज़ होनी चाहिए!

## Meena Bowls | मीना की गेंद
plot: Surya challenges Meena to get him out, Meena runs in fast, his bat swings through air and the ball hits the stumps, and Dadaji catches the rebound.
ending: मीना ने कर दिखाया!
hook: मीना की गेंद पर सूर्या का क्या हाल हुआ? 🎯
- face-off | surya | meena | चैलेंज | surya: मेरा विकेट लेकर दिखाओ! // meena: देखते रहो, सूर्या!
- run-up | meena | surya | | meena: ये ले मेरी तेज़ गेंद! // surya: आराम से खेलूँगा, डरो मत!
- catch | dadaji | surya | meena | dadaji: विकेट से लौटी गेंद मैंने पकड़ ली!
- face-off | surya | meena | आउट | surya: बल्ला हवा में, गेंद विकेट में! // meena: विकेट भी गया, घमंड भी!

## Dadaji's Specs | दादाजी का चश्मा
plot: Dadaji cannot find his glasses, Surya's shot heads his way, Golu shouts that the glasses are on his head, and Dadaji puts them on and catches.
ending: चश्मा मिलते ही नज़र तेज़!
hook: दादाजी का चश्मा आख़िर है कहाँ? 👓
- face-off | dadaji | golu | चश्मा | dadaji: गोलू, मेरा चश्मा कहाँ है? // golu: दादाजी, वह तो आपके सिर पर है!
- shot | surya | dadaji | | surya: दादाजी, सँभलिए, गेंद आ रही है! // dadaji: क्या आ रही है? दिखता नहीं!
- catch | dadaji | surya | golu | dadaji: चश्मा लगाते ही गेंद दिख गई!
- face-off | surya | dadaji | सिर | surya: दादाजी, चश्मा ढूँढने में पूरा दिन! // dadaji: अब चश्मा सिर पर ही रखूँगा!

## Lunch Time | खाने का वक़्त
plot: Aunty calls Meena for lunch, Meena asks for one last ball, Sachin sends it into Aunty's kitchen, and Aunty catches it still holding her rolling pin.
ending: रसोई में छक्का, बेलन तैयार!
hook: आख़िरी गेंद या गरमागरम खाना, मीना क्या चुनेगी? 🍛
- face-off | aunty | meena | खाना | aunty: मीना, खाना ठंडा हो रहा है! // meena: बस आख़िरी गेंद, आंटी!
- shot | sachin | aunty | | sachin: लो, गेंद सीधी रसोई में! // aunty: अरे, मेरी रसोई में छक्का?
- catch | aunty | meena | sachin | aunty: बेलन हाथ में, गेंद भी हाथ में!
- face-off | meena | aunty | रोटी | meena: आंटी, अब तो खाना खा लूँ? // aunty: पहले बेलन से बचो, फिर रोटी!

## Cricket Quiz | क्रिकेट की पहेली
plot: Coach asks a cricket quiz, Golu answers with food, Meena answers with a six, and Coach catches the ball and says that is the right answer.
ending: पहेली हल, गोलू फेल!
hook: कोच का सवाल, गोलू का जवाब, मीना का छक्का! 🤣
- face-off | coach | golu | सवाल | coach: गोलू, विकेट में कितने डंडे? // golu: तीन, और चौथा समोसा!
- shot | meena | golu | | meena: सवाल छोड़ो, ये लो छक्का! // golu: मीना ने जवाब दे दिया!
- catch | coach | golu | meena | coach: सही जवाब पकड़ लिया!
- face-off | coach | golu | नतीजा | coach: गोलू, तुम्हारा जवाब ग़लत है! // golu: कोच जी, समोसे वाला सही था!

## Laddu Plate | लड्डू की थाली
plot: Aunty has counted her laddus, Sachin's shot lands near the plate, Golu says with a full mouth that he ate none, and Aunty catches the ball and recounts.
ending: एक लड्डू कम निकला!
hook: आंटी के गिने हुए लड्डू कैसे कम हो गए? 🍬
- face-off | aunty | golu | लड्डू | aunty: गोलू, लड्डू गिनकर रखे हैं! // golu: मैं तो छुऊँगा भी नहीं!
- shot | sachin | golu | | sachin: शॉट थाली के पास गिरा! // golu: मैं उठा लाता हूँ!
- catch | aunty | golu | sachin | aunty: गेंद पकड़ी, लड्डू भी गिन लिए!
- face-off | aunty | golu | कम | aunty: गोलू, एक लड्डू कम क्यों है? // golu: वो लड्डू ख़ुद चलकर आया!

## Puddle Splash | पानी की छपाक
plot: After the rain Surya warns Sachin about the puddle, Sachin's shot lands in it, Pintu gets soaked along with his whistle, and Aunty catches the ball under her umbrella.
ending: पानी में भी पूरा मज़ा!
hook: गड्ढे में शॉट गया, कौन-कौन भीगा? 💦
- face-off | surya | sachin | गड्ढा | surya: सचिन, गड्ढे के पास मत मारना! // sachin: डर मत, सीधा खेलूँगा!
- shot | sachin | pintu | | sachin: ये गया! // pintu: छपाक! मैं पूरा भीग गया!
- catch | aunty | pintu | sachin | aunty: छाते के नीचे से कैच पकड़ा!
- face-off | pintu | aunty | गीली | pintu: आंटी, मेरी सीटी भी गीली हो गई! // aunty: अब सीटी बजेगी या बहेगी?

## Nap Alarm | दादाजी की झपकी
plot: Dadaji dozes off, Sachin's shot falls in his lap, Dadaji says wide ball without opening his eyes, and throws the ball back.
ending: आँखें बंद, नज़र चालू!
hook: सोते दादाजी की गोद में गेंद आ गिरी! 🥱
- face-off | surya | dadaji | श्श | surya: श्श! दादाजी सो रहे हैं! // dadaji: खर्र, खर्र, खर्र!
- shot | sachin | dadaji | | sachin: धीरे से मारा शॉट! // dadaji: वाइड बॉल!
- catch | dadaji | surya | sachin | dadaji: लो, वापस फेंक दी!
- face-off | surya | dadaji | नींद | surya: दादाजी, आप तो सोते हुए भी अंपायर हो! // dadaji: सोया नहीं, आँखों को आराम दे रहा था!

## Walking Stick | दादाजी की लाठी
plot: Golu has no bat so he borrows Dadaji's walking stick, hits a big shot, and Dadaji catches the ball without his stick.
ending: लाठी बनी बल्ला!
hook: बल्ला न मिला तो गोलू ने क्या उठा लिया? 🤔
- face-off | golu | dadaji | लाठी | golu: दादाजी, आपकी लाठी दे दो! // dadaji: बेटा, लाठी से बल्ला?
- shot | golu | surya | | golu: ये लो लाठी वाला शॉट! // surya: ओहो, गेंद उड़ गई!
- catch | dadaji | golu | surya | dadaji: बिना लाठी के कैच पकड़ लिया!
- face-off | golu | dadaji | बल्ला | golu: दादाजी, आपकी लाठी तो बल्ला बन गई! // dadaji: बेटा, अब मुझे नई लाठी चाहिए!

## Mirror Sun | आईने की धूप
plot: Aunty's mirror throws sunlight into Sachin's eyes, he swings blindly, and Aunty removes the mirror and catches the ball.
ending: शीशे का कमाल!
hook: आईने की धूप ने सचिन को कैसे सताया? 😎
- face-off | sachin | aunty | धूप | sachin: आंटी, शीशा हटाओ, धूप चुभ रही! // aunty: अरे, मैं तो बाल बना रही थी!
- run-up | surya | sachin | | surya: सचिन, तैयार हो? // sachin: आँखें बंद हैं, कुछ दिख नहीं रहा!
- catch | aunty | sachin | surya | aunty: शीशा हटाया, गेंद पकड़ ली!
- face-off | sachin | aunty | चमक | sachin: आंटी, आपका शीशा तो दूसरी धूप है! // aunty: चलो, अगली बार छाँव में खेलो!

## Late Coach | देर से आए कोच
plot: Coach arrives late with samosas, the kids are already playing, Meena's shot comes at him, and he catches it with a samosa in the other hand.
ending: चटनी के साथ समोसा हिट!
hook: देर से आए कोच, हाथ में समोसा! 😋
- face-off | coach | meena | देर | coach: माफ़ करना, समोसे लेने गया था! // meena: कोच जी, हम तो खेल चुके!
- run-up | golu | meena | | golu: समोसे की ख़ुशबू आ रही है! // meena: पहले गेंद, फिर समोसे!
- catch | coach | golu | meena | coach: एक हाथ में समोसा, दूसरे में कैच!
- face-off | golu | coach | समोसा | golu: कोच जी, समोसा गिरा तो मेरा! // coach: कैच पक्का, समोसा आधा-आधा!

## Wrong Name | ग़लत नाम
plot: Pintu mixes up the boys' names, Sachin insists on his own name, Surya asks if he is out then, and Coach catches the ball and sorts out the names.
ending: सबके नाम अब पक्के!
hook: अंपायर को सबके नाम गड़बड़ क्यों लगे? 🧐
- face-off | pintu | sachin | आउट | pintu: तुम आउट हो, तुम्हीं! // sachin: अंपायर साहब, पहले मेरा नाम तो पूछिए!
- run-up | surya | sachin | | surya: तो फिर आउट मैं हुआ क्या? // sachin: तू भी नहीं, अंपायर को कुछ पता नहीं!
- catch | coach | pintu | surya | coach: रुको! पहले नाम सुधारो, फिर आउट!
- face-off | pintu | sachin | सूची | pintu: ठीक है, नामों की सूची बनाऊँगा! // sachin: और उसमें मेरा नाम सबसे ऊपर!

## Lucky Cap | क़िस्मत वाली टोपी
plot: Surya wears his lucky cap, the wind blows it away, he chases the cap instead of hitting, and Pintu catches the cap instead of the ball.
ending: टोपी उड़ी, क़िस्मत भी!
hook: क़िस्मत वाली टोपी हवा में उड़ गई, अब? 🧢
- face-off | surya | sachin | टोपी | surya: यह टोपी मेरे लिए शुभ है! // sachin: हवा को तो पता ही नहीं!
- run-up | sachin | surya | | sachin: गेंद आ रही है! // surya: अरे, मेरी टोपी उड़ गई!
- catch | pintu | surya | sachin | pintu: मैंने गेंद नहीं, टोपी पकड़ ली!
- face-off | surya | pintu | क़िस्मत | surya: पिंटू, मेरी टोपी दो! // pintu: लो, पर क़िस्मत अब भी हवा में!

## Kulfi Bell | कुल्फ़ी की घंटी
plot: The kulfi seller's bell rings, every player runs off, Sachin's last shot goes up, and Dadaji, left alone, catches it.
ending: घंटी बजी, मैदान सूना!
hook: कुल्फ़ी की घंटी बजी, मैदान किसने छोड़ा? 🍦
- face-off | golu | meena | कुल्फ़ी | golu: सुनो! कुल्फ़ी वाले की घंटी! // meena: चलो, सब भागो!
- shot | sachin | golu | | sachin: आख़िरी शॉट, फिर कुल्फ़ी! // golu: जल्दी करो, कुल्फ़ी पिघल जाएगी!
- catch | dadaji | golu | meena | dadaji: सब चले गए, मैंने अकेले पकड़ ली!
- face-off | sachin | dadaji | ठंडा | sachin: दादाजी, आपके लिए भी कुल्फ़ी लाए! // dadaji: गेंद पकड़ी मैंने, कुल्फ़ी खाई तुमने!

## Golu's Commentary | गोलू की कमेंट्री
plot: Golu does commentary with a stick as a microphone, calls Meena's six a four, Sachin corrects him, and Aunty catches the ball and takes the microphone.
ending: माइक गया, कमेंट्री ख़त्म!
hook: गोलू की कमेंट्री में चौका या छक्का? 🎤
- face-off | golu | sachin | कमेंट्री | golu: अब सुनिए आँखों देखा हाल! // sachin: गोलू, पहले बल्ला तो पकड़ने दे!
- shot | meena | golu | | meena: देखो, गेंद सीमा पार! // golu: और यह गया चौका!
- catch | aunty | golu | sachin | aunty: गेंद भी मेरी, माइक भी मेरा!
- face-off | sachin | golu | विराम | sachin: गोलू, तेरी कमेंट्री बंद! // golu: अब थोड़ा विराम, फिर मिलेंगे!

## Tomato Ball | टमाटर की गेंद
plot: Surya forgets the ball and bowls a tomato, Sachin's shot splashes it over Pintu, and Aunty catches what is left and sends everyone to wash.
ending: टमाटर की चटनी बन गई!
hook: गेंद की जगह टमाटर? अंपायर का क्या हुआ? 🍅
- face-off | sachin | surya | गेंद | sachin: सूर्या, गेंद कहाँ है? // surya: गेंद नहीं मिली, टमाटर चलेगा!
- run-up | surya | sachin | | surya: ये ले टमाटर वाली गेंद! // sachin: इसे बल्ले से मारूँ क्या?
- shot | sachin | pintu | | sachin: लो, टमाटर हवा में! // pintu: छपाक! मैं तो टमाटर से लाल हो गया!
- face-off | aunty | pintu | चटनी | aunty: बचा टमाटर मेरा, सब नहाने जाओ! // pintu: आंटी, आज चटनी में अंपायर भी है!

## Bucket Stumps | बाल्टी का विकेट
plot: There are no stumps so Aunty's bucket becomes the wicket, the ball splashes into the bucket, and Aunty fishes it out of the water.
ending: बाल्टी हुई विकेट, आंटी नाराज़!
hook: आंटी की बाल्टी बनी विकेट, गेंद कहाँ गिरी? 💧
- face-off | aunty | meena | बाल्टी | aunty: मीना, मेरी बाल्टी विकेट नहीं है! // meena: आंटी, बस पाँच मिनट के लिए!
- run-up | meena | surya | | meena: सीधा बाल्टी पर निशाना! // surya: मैं चूक गया, गेंद बाल्टी में!
- catch | aunty | meena | surya | aunty: पानी से गेंद निकालकर पकड़ी!
- face-off | meena | aunty | पानी | meena: आंटी, विकेट भी बाल्टी का, पानी भी! // aunty: अब बाल्टी भरकर लाओ, दोनों!

<!-- auto-written 2026-11-10 by gemini/gemini-3.5-flash; passed the same checks as hand-written stories + editor grade >= 7 -->

## Dog Coaching | कुत्ते की कोचिंग
plot: Surya tries to teach Bruno how to field, Sachin hits a soft shot, but Bruno catches the ball and passes it directly to Aunty.
ending: ब्रूनो बना आंटी का चेला!
hook: कुत्ते की कोचिंग में ग़लती किसकी थी? 🐶
- face-off | surya | golu | फ़ील्ड | surya: आज तुझे फ़ील्डिंग सिखाऊँगा! // golu: ये तो बस भौंकता है!
- shot | sachin | golu | | sachin: ये लो मेरा धीमा शॉट! // golu: अब कैच पकड़ो!
- catch | aunty | bruno | golu | aunty: शाबाश ब्रूनो, गेंद मुझे दी! // bruno: भौं भौं!
- face-off | surya | aunty | पास | surya: अरे, मुझे गेंद देनी थी! // aunty: ये तो अब मेरा फ़ीलडर है!

<!-- auto-written 2026-11-12 by gemini/gemini-3.5-flash; passed the same checks as hand-written stories + editor grade >= 7 -->

## Begum Bridge Four | बेगम पुल का चौका
plot: Mintu claims the ball touched the Begum Bridge wall for a four, but Golu spots Bruno sitting on the ball, and Pintu gives Mintu out.
ending: चौके का लालच पड़ा भारी!
hook: मिंटू का बेगम पुल वाला प्लान उल्टा पड़ गया! 😜
card: चौका या आउट?
- face-off | mintu | pintu | नियम | mintu: बेगम पुल की दीवार छुई, चौका हुआ!
- shot | mintu | golu | | mintu: हमारी गली का नियम है! // golu: गेंद वहाँ नहीं गई!
- catch | pintu | golu | bruno | bruno: भौं भौं! // golu: देखो! गेंद पर ब्रूनो बैठा है!
- face-off | pintu | mintu | आउट | pintu: फ़ैसला मेरा, मिंटू तुम आउट! // mintu: यह तो बेईमानी है!

## Bruno the Umpire | ब्रूनो अंपायर
plot: With the umpire's stool empty, Bruno sits on it and signals out at every swing, Sachin argues, and then Bruno's tail knocks the bails for a real out.
ending: अंपायर ब्रूनो ज़िंदाबाद!
hook: ब्रूनो ने किसे आउट दे दिया? 🐶
card: ब्रूनो का आउट!
- face-off | sachin | bruno | आउट | sachin: ब्रूनो, मैं आउट नहीं हूँ!
- run-up | surya | sachin | | surya: देख, ये मेरी रफ़्तार!
- shot | sachin | bruno | | sachin: ये छक्का, अब मत कहना आउट!
- face-off | bruno | sachin | गिल्ली | sachin: पूँछ से गिल्ली गिरी, सच में आउट!

## Bruno the Detective | ब्रूनो जासूस
plot: The ball is lost in a storm, Bruno sniffs his way to Aunty's kitchen, and Golu finds the ball sitting in the dough.
ending: आटे की गेंद, रोटी रानी!
hook: तूफ़ान में खोई गेंद कहाँ मिली? 🔍
card: गेंद कहाँ गई?
- face-off | golu | aunty | गेंद | golu: आंटी, हमारी गेंद आपके घर में है! // aunty: यहाँ कुछ नहीं है!
- run-up | meena | golu | | meena: तूफ़ान में गेंद गुम हुई!
- shot | golu | bruno | | golu: ब्रूनो सूँघता रसोई चला!
- face-off | aunty | golu | आटा | golu: आंटी, गेंद आटे में बैठी है! // aunty: हाय, अब रोटी का क्या होगा?

## Bruno vs Pigeon | ब्रूनो और कबूतर
plot: A pigeon sits on the stumps and Bruno scares it away just as Surya bowls, so the ball hits the empty stumps and Sachin is bowled.
ending: कबूतर की मेहरबानी से आउट!
hook: कबूतर की वजह से कौन आउट हुआ? 🐦
card: स्टंप्स पर कबूतर!
- face-off | sachin | bruno | कबूतर | sachin: स्टंप पर कबूतर बैठा है!
- run-up | surya | sachin | | surya: कबूतर उड़ा, अब मेरी गेंद!
- shot | sachin | bruno | | sachin: अरे, गिल्लियाँ उड़ गईं!
- face-off | surya | sachin | बोल्ड | surya: कबूतर उड़ा, तू भी उड़ गया! // sachin: ये तो सरासर धोखा है!

## Bruno Bats | ब्रूनो की बल्लेबाज़ी
plot: Bruno grabs the dropped bat to chase the ball and accidentally hits a six, and then Coach and Meena both claim it was their coaching.
ending: छक्का ब्रूनो का, श्रेय कोच!
hook: ब्रूनो के छक्के का श्रेय किसे मिला? 🏏
card: ब्रूनो ने मारा छक्का!
- face-off | meena | coach | बल्ला | meena: कोच जी, हमारा बल्ला उड़ गया! // coach: अरे, उसे रोको!
- run-up | meena | surya | | meena: सूर्या, तू गेंद फेंक!
- shot | surya | bruno | | surya: ब्रूनो ने छक्का मार दिया!
- face-off | coach | meena | शाबाश | coach: मैंने ही सिखाया था! // meena: नहीं कोच जी, मैंने सिखाया!

## Bruno Hides the Ball | ब्रूनो ने गेंद छुपाई
plot: Bruno buries the ball in Aunty's flower pot, and Aunty proudly shows her ball plant to Golu and the whole gali.
ending: गमला बना गेंद का घर!
hook: आंटी के गमले में ये क्या उगा? 🌱
card: गमले में गेंद!
- face-off | golu | bruno | गमला | golu: ब्रूनो, हमारी गेंद कहाँ छुपाई?
- run-up | sachin | golu | | sachin: गोलू, गमले में कुछ चमका!
- shot | golu | aunty | | golu: आंटी, आपके गमले में गेंद है! // aunty: अरे वाह, मेरा पौधा फला!
- face-off | aunty | golu | पौधा | aunty: देखो सब, मेरा गेंद वाला पौधा! // golu: आंटी, ये गेंद चोर का काम है!

## Bruno and the Cooker Whistle | ब्रूनो और कुकर सीटी
plot: Every cooker whistle from Aunty's kitchen makes Bruno run to the pitch thinking it is Pintu's whistle, and Pintu tells him it was not his.
ending: कुकर की सीटी, ब्रूनो हाज़िर!
hook: कुकर की आवाज़ पर ब्रूनो क्यों भागा? 🍲
card: सीटी बजी, ब्रूनो भागा!
- face-off | pintu | bruno | सीटी | pintu: ब्रूनो, ये मेरी सीटी नहीं थी!
- run-up | surya | sachin | | surya: कुकर फिर बजा, कुत्ता फिर आया!
- shot | sachin | aunty | | aunty: मेरा कुकर बजा, मैदान भर गया! // sachin: आंटी, आपकी सीटी भारी है!
- face-off | bruno | pintu | मैदान | pintu: अब बाहर जा, फ़ील्डिंग मत कर!

## Bruno Guards the Wicket | ब्रूनो पहरेदार
plot: Bruno lies in front of the stumps so no one can bowl, and when Surya bribes him with a biscuit he takes it and still does not move.
ending: बिस्कुट लिया, जगह नहीं छोड़ी!
hook: बिस्कुट लेकर भी ब्रूनो क्यों नहीं हिला? 🍪
card: ब्रूनो हटता ही नहीं!
- face-off | surya | bruno | बिस्कुट | surya: ब्रूनो, स्टंप के सामने से हटो!
- run-up | surya | golu | | surya: ये बिस्कुट ले, रास्ता छोड़!
- shot | golu | bruno | | golu: बिस्कुट खा गया, फिर भी जमा!
- face-off | surya | bruno | सौदा | surya: ब्रूनो तो पक्का सौदेबाज़ निकला!

## Bruno's Rooftop Rescue | ब्रूनो की छत
plot: The ball lands on the roof, Bruno climbs the stairs and rolls it back down, and it drops right into Dadaji's lap while Golu cheers.
ending: गेंद दादाजी की गोद में!
hook: छत की गेंद ब्रूनो ने कैसे लौटाई? 🏠
card: गेंद छत पर फँसी!
- face-off | golu | dadaji | छत | golu: दादाजी, हमारी गेंद छत पर गई! // dadaji: सीढ़ियाँ कौन चढ़ेगा?
- run-up | golu | sachin | | golu: देखो, कोई ऊपर चढ़ गया!
- shot | sachin | bruno | | sachin: ब्रूनो गेंद लुढ़का रहा है!
- catch | dadaji | golu | | dadaji: लो, गेंद मेरी गोद में आई! // golu: छत से डाक आ गई!

## Bruno Chooses a Team | ब्रूनो किसकी टीम
plot: Both captains Pappu and Sachin call Bruno to their team, and he sits on the line between them until Aunty's samosa plate settles it.
ending: समोसे ने जिताई टीम!
hook: दोनों टीमों ने बुलाया, ब्रूनो किधर गया? 🥟
card: ब्रूनो किसकी टीम में?
- face-off | pappu | bruno | टीम | pappu: ब्रूनो, तू मेरी टीम में खेलेगा!
- run-up | pappu | sachin | | sachin: नहीं पप्पू, वो मेरी टीम में है!
- shot | sachin | bruno | | sachin: ब्रूनो तो लाइन पर बैठा है!
- face-off | aunty | bruno | समोसा | aunty: ये समोसे किसके लिए हैं?

## Bruno the Ball Boy | ब्रूनो बॉल बॉय
plot: Bruno fetches every ball so fast that the match ends in five minutes, and Coach is confused while Sachin just laughs.
ending: मैच पाँच मिनट में खत्म!
hook: ब्रूनो ने मैच इतनी जल्दी क्यों निपटाया? 🏃
card: मैच जल्दी खत्म हुआ!
- face-off | coach | sachin | मैच | coach: सचिन, मैच खत्म कैसे हो गया?
- run-up | coach | sachin | | coach: ये गेंद फेंक रहा हूँ!
- shot | sachin | bruno | | sachin: ब्रूनो हर गेंद फ़ौरन ले आता है!
- face-off | coach | bruno | दौड़ | coach: ब्रूनो, ज़रा आराम से लाया कर!

## Bruno and the Kite | ब्रूनो और पतंग
plot: A kite string wraps around the ball, Mintu and Golu panic, and Bruno pulls the kite down so the ball comes along with it.
ending: पतंग उतरी, गेंद भी!
hook: पतंग में अटकी गेंद कैसे उतरी? 🪁
card: गेंद पतंग में उलझी!
- face-off | mintu | golu | पतंग | mintu: गोलू, गेंद डोर में उलझ गई! // golu: इसे नीचे कौन लाएगा?
- run-up | golu | mintu | | golu: डोर खींच, मैं गेंद पकड़ूँगा!
- shot | mintu | bruno | | mintu: ब्रूनो ने पतंग पकड़ ली!
- face-off | golu | mintu | गेंद | golu: देखो, पतंग के साथ गेंद आई! // mintu: शाबाश, पतंग वाले हीरो!

## Bruno Learns Howzat | ब्रूनो का हाउज़ैट
plot: Golu teaches Bruno to say howzat, but at the worst moment Bruno barks and Pintu takes it as an appeal and gives Sachin out.
ending: भौंकने पर आउट दे दिया!
hook: ब्रूनो के भौंकने पर सचिन आउट क्यों हुआ? 🙋
card: ब्रूनो की अपील!
- face-off | golu | bruno | अपील | golu: ब्रूनो, ज़ोर से बोलो हाउज़ैट!
- run-up | golu | sachin | | golu: सचिन, ये गेंद संभालना!
- shot | sachin | pintu | | sachin: देखो, मेरा ज़ोरदार शॉट! // pintu: आउट! अपील हुई है!
- face-off | sachin | pintu | फ़ैसला | sachin: वो तो भौंका था! // pintu: मुझे हाउज़ैट सुनाई दिया!

## Bruno at the Power Cut | ब्रूनो और बिजली गई
plot: When the lights go off, only the glow of Bruno's collar shows the ball in the dark, and Dadaji and Meena follow it down the gali.
ending: चमकती पट्टी ने राह दिखाई!
hook: अँधेरे में गेंद कैसे मिली? 💡
card: बिजली गई, गेंद गुम!
- face-off | dadaji | meena | अँधेरा | dadaji: मीना, बिजली गई और गेंद गुम! // meena: दादाजी, वो चमकती पट्टी देखो!
- run-up | meena | sachin | | meena: सचिन, चमक के पीछे चलो!
- shot | sachin | bruno | | sachin: ब्रूनो, तेरी पट्टी तो टॉर्च है!
- face-off | meena | dadaji | रोशनी | meena: देखो, गेंद पट्टी के पास है!

## Bruno Swaps the Ball | ब्रूनो की बदली
plot: Bruno brings a lemon instead of the ball, nobody notices until Surya bowls it and lemon juice splashes on Chhotu.
ending: गेंद की जगह नींबू!
hook: ब्रूनो ने गेंद की जगह क्या रख दिया? 🍋
card: गेंद नहीं, नींबू है!
- face-off | chhotu | bruno | नींबू | chhotu: ब्रूनो, ये गेंद हरी-पीली क्यों है?
- run-up | surya | chhotu | | surya: चलो, ये गेंद फेंकता हूँ!
- shot | chhotu | surya | | chhotu: अरे, रस मेरे मुँह पर गिरा! // surya: ये तो नींबू निकला!
- face-off | surya | bruno | रस | surya: ब्रूनो, तूने नींबू क्यों दिया?

## Bruno Steals Mintu's Ball | ब्रूनो ने मिंटू की गेंद उड़ाई
plot: Mintu sneaks a better ball into the game, Bruno sniffs it as not ours, and takes it back to Chhotu's shop.
ending: बेईमानी की गेंद दुकान पहुँची!
hook: मिंटू की चोरी की गेंद कहाँ गई? 🕵
card: मिंटू की गेंद उड़ी!
- face-off | chhotu | mintu | गेंद | chhotu: मिंटू, ये गेंद मेरी दुकान की है! // mintu: नहीं, ये हमारी है!
- run-up | mintu | surya | | mintu: चलो, इसी गेंद से खेलो!
- shot | surya | bruno | | surya: अरे, ब्रूनो गेंद ले गया!
- face-off | mintu | chhotu | दुकान | mintu: गेंद वापस दुकान पहुँच गई! // chhotu: अब पता चला किसकी है!

## Bruno on the Scoreboard | ब्रूनो का स्कोरबोर्ड
plot: Bruno steps on the chalk score and leaves paw prints, so Pintu and Golu look at the board and the score becomes six paws.
ending: स्कोर में पंजे ही पंजे!
hook: स्कोरबोर्ड पर ये पंजे किसके निकले? 🐾
card: स्कोर पर पंजे!
- face-off | pintu | golu | स्कोर | pintu: गोलू, स्कोर पर पंजे छप गए!
- run-up | golu | sachin | | golu: अब स्कोर कैसे गिनूँगा?
- shot | sachin | bruno | | sachin: ब्रूनो, तूने सब मिटा दिया!
- face-off | golu | pintu | पंजे | golu: अब स्कोर छह पंजे हुआ! // pintu: चलो, यही लिख देते हैं!

## Bruno the Slip Fielder | ब्रूनो स्लिप में
plot: Bruno stands in the slips and catches the ball in his mouth, so Sachin is out and Coach gives Bruno a biscuit.
ending: कुत्ते को मिला इनाम!
hook: स्लिप में खड़े ब्रूनो ने क्या पकड़ा? 🧤
card: ब्रूनो स्लिप में खड़ा!
- face-off | coach | bruno | स्लिप | coach: ब्रूनो स्लिप में खड़ा है, संभलकर!
- run-up | coach | sachin | | coach: ध्यान रखना, गेंद तेज़ आ रही है!
- shot | sachin | bruno | | sachin: ये लो चौका!
- face-off | coach | bruno | बिस्कुट | coach: ब्रूनो, बिस्कुट पक्का है!

## Bruno vs the Auto | ब्रूनो और ऑटो
plot: An auto honk scares Bruno and he runs off with the ball through the market, and Chhotu and Pappu start a relay to get it back.
ending: बाज़ार में गेंद की रेस!
hook: हॉर्न सुनकर ब्रूनो गेंद लेकर कहाँ भागा? 🛺
card: ब्रूनो गेंद लेकर भागा!
- face-off | pappu | chhotu | हॉर्न | pappu: छोटू, गेंद लेकर कोई भागा! // chhotu: ऑटो के हॉर्न से डरा!
- run-up | chhotu | pappu | | chhotu: पप्पू भैया, उसे पकड़ो!
- shot | pappu | bruno | | pappu: रुक जा, गेंद वापस दे!
- face-off | chhotu | pappu | रिले | chhotu: दुकानदार भी दौड़ रहे हैं! // pappu: पूरा बाज़ार दौड़ रहा है!

## Bruno's Birthday | ब्रूनो का जन्मदिन
plot: The gali plans a surprise party for Bruno, Bruno finds the cake early, and Pappu ends up wearing the cake while Meena laughs.
ending: केक पप्पू की शर्ट पर!
hook: सरप्राइज़ पार्टी में असली सरप्राइज़ क्या निकला? 🎉
card: ब्रूनो का केक गायब!
- face-off | meena | pappu | केक | meena: पप्पू भैया, जन्मदिन का केक कहाँ गया?
- run-up | meena | sachin | | meena: सचिन, पार्टी की गेंद फेंक!
- shot | pappu | bruno | | pappu: अरे, मेरी शर्ट पर केक लग गया!
- face-off | meena | bruno | मज़ा | meena: सरप्राइज़ तो ब्रूनो ने दे दिया!

## Bruno and the Rain | ब्रूनो और बारिश
plot: It starts raining, and Bruno shakes the water off his coat onto Pintu just as Surya asks for a decision.
ending: ब्रूनो ने किया छिड़काव!
hook: बारिश में ब्रूनो ने पिंटू को क्या किया? 🌧
card: बारिश और ब्रूनो!
- face-off | surya | pintu | बारिश | surya: पिंटू, बारिश आ गई, फ़ैसला दो! // pintu: ठहरो, पहले सोचने दो!
- run-up | surya | golu | | surya: गोलू, गेंद संभालकर रखना!
- shot | golu | bruno | | golu: ब्रूनो, तू तो पूरा भीग गया!
- face-off | pintu | bruno | भीगा | pintu: कपड़े तक गीले हो गए!

## Bruno Finds the Bat | ब्रूनो को बल्ला मिला
plot: The only bat is missing, so Bruno brings Dadaji's walking stick and Sachin goes on playing with Dadaji's stick as a bat.
ending: लाठी ने सँभाली पारी!
hook: बल्ला गुम हुआ तो ब्रूनो क्या लाया? 🦯
card: बल्ला कहाँ गया?
- face-off | sachin | dadaji | लाठी | sachin: दादाजी, हमारा बल्ला खो गया! // dadaji: ये लो, मेरी लाठी!
- run-up | surya | sachin | | surya: अब इस लाठी से खेलो!
- shot | sachin | bruno | | sachin: लाठी से भी छक्का!
- face-off | dadaji | sachin | छक्का | dadaji: मेरी लाठी में दम है! // sachin: दादाजी, आपकी लाठी कमाल निकली!

## Bruno Teaches Surya | ब्रूनो सिखाए सूर्या को
plot: Surya cannot bowl straight, so Bruno runs along the pitch and Surya finally bowls where Bruno points while Coach watches.
ending: सीधी गेंद, सीख ब्रूनो की!
hook: सूर्या को सीधी गेंद किसने सिखाई? 🎯
card: सूर्या की टेढ़ी गेंद!
- face-off | coach | surya | गेंद | coach: सूर्या, तेरी गेंद टेढ़ी जाती है! // surya: कोच जी, मैं तो सीधी फेंकता हूँ!
- run-up | surya | sachin | | surya: जहाँ दौड़ेगा, वहीं फेंकूँगा!
- shot | sachin | bruno | | sachin: इस बार गेंद सीधी आई!
- face-off | surya | coach | निशाना | surya: कोच जी, सिखाने वाला कौन निकला? // coach: अब वही मेरा कोच है!

## Bruno and the Tiffin | ब्रूनो और टिफ़िन
plot: Bruno steals Golu's tiffin, and when Aunty opens it she finds the cricket ball that Golu had hidden from his mother.
ending: टिफ़िन खुला, पोल खुली!
hook: गोलू के टिफ़िन में क्या छुपा था? 🍱
card: टिफ़िन में क्या है?
- face-off | golu | bruno | टिफ़िन | golu: ब्रूनो, ये मेरा खाना है!
- run-up | surya | golu | | surya: जल्दी कर!
- shot | golu | aunty | | golu: आंटी, मेरा टिफ़िन किसी ने उठा लिया! // aunty: ला, मैं देखूँ इसमें क्या है!
- face-off | aunty | golu | गेंद | aunty: अरे, इसमें तो क्रिकेट की गेंद है! // golu: आंटी, मम्मी को मत बताना!

## Bruno Brings a Friend | ब्रूनो अपना दोस्त लाया
plot: Bruno brings a small puppy to the match, Meena says it fields badly but cutely, and Coach agrees to keep both.
ending: दो दोस्त, एक परिवार!
hook: ब्रूनो मैच में किसे साथ ले आया? 🐕
card: ब्रूनो का नया दोस्त!
- face-off | meena | coach | पिल्ला | meena: कोच जी, ये छोटा पिल्ला कौन है? // coach: कोई इसे लाया है!
- run-up | meena | surya | | meena: सूर्या, पिल्ले को मत मारना!
- shot | surya | bruno | | surya: ये नन्हा तो गेंद के पीछे गिर गया!
- face-off | coach | meena | मंज़ूर | coach: दोनों टीम में रहेंगे! // meena: कोच जी, आप तो दिलदार निकले!

## Dadaji's Catch Rule | दादाजी का नियम
plot: Dadaji makes a rule that any ball reaching his chair is out, and Sachin tries to hit away from it but the ball still lands with Dadaji while Surya bowls.
ending: नियम पक्का, बल्लेबाज़ हैरान!
hook: दादाजी की कुर्सी पर कौन फँसा? 👴
card: दादाजी का नियम!
- face-off | dadaji | sachin | नियम | dadaji: जो गेंद कुर्सी तक आए, आउट! // sachin: दादाजी, ये कैसा नियम?
- run-up | surya | sachin | | surya: अब उलटी तरफ़ मारकर दिखा!
- shot | sachin | dadaji | | sachin: इस बार कुर्सी से दूर मारा!
- catch | dadaji | sachin | surya | dadaji: फिर भी गेंद मेरी गोद में! // sachin: दादाजी, गेंद तो जादूगर है!

## Dadaji Sleeps | दादाजी सो गए
plot: Dadaji sleeps in his chair and every ball lands softly in his lap, and when he wakes he says it is his ball while Golu and Sachin laugh.
ending: खर्राटे वाला कैच!
hook: खर्राटों के बीच गेंद दादाजी तक कैसे पहुँची? 😴
card: दादाजी सो गए!
- face-off | golu | dadaji | नींद | golu: दादाजी सो गए, गेंद उनकी गोद में!
- run-up | sachin | golu | | sachin: गोलू, धीरे से गेंद उठा ला!
- shot | golu | dadaji | | golu: दादाजी तो खर्राटे ले रहे हैं!
- catch | dadaji | golu | sachin | dadaji: ये गेंद तो मेरी है! // golu: दादाजी, आप जाग गए?

## Dadaji's Old Bat | दादाजी का पुराना बल्ला
plot: Dadaji brings his heavy old bat, Surya hits a six that nobody can explain, and Pintu says Dadaji just smiles and says it was like in his time.
ending: पुराना बल्ला, नया धमाका!
hook: दादाजी का भारी बल्ला क्या चमत्कार कर गया? 🏏
card: दादाजी का पुराना बल्ला!
- face-off | surya | dadaji | बल्ला | surya: दादाजी, ये बल्ला बहुत भारी है! // dadaji: हमारे ज़माने में यही चलता था!
- run-up | sachin | surya | | sachin: संभल, तेज़ गेंद आ रही!
- shot | surya | pintu | | surya: पूरा ज़ोर लगाकर छक्का! // pintu: गेंद छत के पार!
- face-off | dadaji | pintu | मुस्कान | pintu: दादाजी, ये कैसे हुआ? // dadaji: बेटा, ये हमारा ज़माना!

## Dadaji Keeps Score | दादाजी का हिसाब
plot: Dadaji keeps the whole score in his head and corrects Pintu and Golu every time they count wrong.
ending: दादाजी का दिमाग, कैलकुलेटर!
hook: स्कोर में गलती दादाजी ने कैसे पकड़ी? 🧮
card: दादाजी का हिसाब!
- face-off | pintu | dadaji | हिसाब | pintu: स्कोर पचास है, दादाजी! // dadaji: नहीं, उनचास है!
- run-up | golu | sachin | | golu: मैंने भी पचास गिना था!
- shot | sachin | dadaji | | sachin: दादाजी तो हमेशा सही निकलते हैं!
- face-off | dadaji | golu | सही | dadaji: गिनती सीख, गोलू बेटा! // golu: दादाजी, आप तो मशीन हो!

## Dadaji vs Aunty | दादाजी बनाम आंटी
plot: Dadaji and Aunty argue over whose chair the ball hit, until Bruno sits down in both of them.
ending: दोनों कुर्सी, एक कुत्ता!
hook: कुर्सी की लड़ाई कौन जीता? 🪑
card: कुर्सी किसकी है?
- face-off | dadaji | aunty | कुर्सी | dadaji: आंटी, गेंद मेरी कुर्सी पर लगी! // aunty: नहीं दादाजी, मेरी कुर्सी पर!
- run-up | golu | sachin | | golu: अब दोनों में झगड़ा हो गया!
- shot | sachin | bruno | | sachin: ब्रूनो दोनों कुर्सी पर चढ़ गया!
- face-off | aunty | dadaji | समझौता | aunty: अब कौन सी कुर्सी मेरी है? // dadaji: दोनों में कुत्ता बैठा है!

## Coach's Whistle Mistake | कोच की सीटी
plot: Coach blows the whistle by mistake and the whole team freezes mid-bowl, so Surya's ball stops in his hand while Sachin waits.
ending: सीटी बजी, सब जम गए!
hook: कोच की एक सीटी से सबको क्या हुआ? 📣
card: सीटी बजी, सब जमे!
- face-off | coach | surya | सीटी | coach: ग़लती से सीटी बज गई! // surya: सब रुक गए, कोच जी!
- run-up | surya | sachin | | surya: गेंद मेरे हाथ में अटक गई!
- shot | sachin | coach | | sachin: मैं बल्ला उठाए खड़ा हूँ!
- face-off | coach | surya | फ्रीज़ | coach: अब दोबारा सीटी बजाऊँ? // surya: नहीं कोच जी, मत बजाना!

## Coach Demonstrates | कोच दिखाए
plot: Coach shows Sachin and Meena how to bat and misses ten times in a row, then hits a six and pretends he planned it.
ending: कोच का छक्का, पक्की प्लानिंग!
hook: कोच ने बल्लेबाज़ी कैसे सिखाई? 🎓
card: कोच ने दिखाया बल्ला!
- face-off | coach | meena | सबक | coach: देखो मीना, ऐसे बल्ला घुमाते हैं! // meena: कोच जी, गेंद निकल गई!
- run-up | meena | sachin | | meena: सचिन, गेंद डाल, मैं देखूँगी!
- shot | sachin | coach | | sachin: कोच जी का बल्ला खाली गया!
- face-off | coach | sachin | प्लान | coach: छक्का भी मैंने सोचा था! // sachin: हाँ कोच जी, बिल्कुल!

## Coach's Big Laugh | कोच की हँसी
plot: Coach laughs so loudly that the ball bounces off the wall, and Pintu calls it a six while Surya argues.
ending: हँसी की गूँज, हँगामा!
hook: कोच की हँसी से गेंद कहाँ पहुँची? 😆
card: कोच की ज़ोरदार हँसी!
- face-off | coach | surya | हँसी | coach: हा हा हा, तेरा चुटकुला मज़ेदार था!
- run-up | surya | sachin | | surya: गेंद दीवार से टकरा गई!
- shot | sachin | pintu | | sachin: ये तो चौका है! // pintu: नहीं, सीधा छक्का दिया!
- face-off | surya | pintu | फ़ैसला | surya: पिंटू, हँसी पर छक्का कहाँ लिखा है? // pintu: मेरा फ़ैसला है!

## Coach's Diet | कोच की डाइट
plot: Coach says no sweets for the players, then Aunty brings jalebi and Coach is first in the line while Golu watches.
ending: डाइट गई, जलेबी आई!
hook: मिठाई मना थी, कोच कहाँ पहुँचे? 🍥
card: कोच की डाइट टूटी!
- face-off | coach | golu | मिठाई | coach: आज से सबकी मिठाई बंद! // golu: जी कोच जी!
- run-up | golu | sachin | | golu: गरम जलेबी लेकर कोई आ रही है!
- shot | sachin | aunty | | aunty: गरम जलेबी, पहले मैं किसे दूँ?
- face-off | coach | aunty | जलेबी | coach: आंटी, पहले मुझे दीजिए! // aunty: कोच जी, आपकी डाइट कहाँ गई?

## Coach vs Meena | कोच बनाम मीना
plot: Coach says girls cannot hit sixes, Meena hits two in a row, and he claims he only said it to motivate her.
ending: मीना जीती, हौसला बढ़ा!
hook: कोच की बात पर मीना ने क्या किया? 🏆
card: मीना बनाम कोच!
- face-off | coach | meena | चुनौती | coach: मीना, तू छक्का नहीं मार सकती! // meena: कोच जी, देखते रहिए!
- run-up | coach | meena | | coach: लो, खेलकर दिखाओ!
- shot | meena | pintu | | meena: पहला छक्का! // pintu: दूसरा भी गया!
- face-off | coach | meena | हौसला | coach: मैंने तो बस हौसला बढ़ाया था! // meena: हाँ कोच जी, समझ गए!

## Coach's Net Practice | कोच की नेट
plot: Coach ties a net between two poles and Sachin hits a ball right through it and onto Dadaji.
ending: नेट फटी, दादाजी हँसे!
hook: कोच की नेट में छेद किसने किया? 🥅
card: कोच की नई नेट!
- face-off | coach | sachin | नेट | coach: देखो, मेरी नेट कितनी मज़बूत है!
- run-up | coach | sachin | | coach: अब ये गेंद मारकर दिखा!
- shot | sachin | dadaji | | sachin: नेट फाड़ दी, दादाजी पकड़ो!
- catch | dadaji | sachin | coach | dadaji: कोच जी, आपकी नेट फट गई! // coach: मेरी मेहनत बेकार गई!

## Coach's Late Day | कोच देर से
plot: Coach arrives late and Pappu and Meena have already made their own rules and refuse to change them.
ending: देर से आए, नियम गँवाए!
hook: कोच देर से आए तो क्या मिला? 🕘
card: कोच देर से आए!
- face-off | coach | pappu | नियम | coach: ये सब नियम किसने बनाए हैं? // pappu: हमने बनाए हैं, कोच जी!
- run-up | pappu | meena | | pappu: पहली गेंद मैं डालूँगा!
- shot | meena | coach | | meena: कोच जी, अब हमारे नियम चलेंगे!
- face-off | coach | pappu | मंज़ूर | coach: ठीक है, आज तुम्हारी टीम जीती! // pappu: धन्यवाद, आज हमारा दिन!

## Coach's Motivation | कोच का भाषण
plot: Coach gives a long speech before the match, Surya and Sachin listen patiently, and by the end it starts raining so the game is over.
ending: भाषण लंबा, मैच बारिश में!
hook: कोच के भाषण के बाद मैच का क्या हुआ? 🎤
card: कोच का लंबा भाषण!
- face-off | coach | surya | भाषण | coach: आज हम जीतकर दिखाएँगे! // surya: कोच जी, बारिश आ रही है!
- run-up | surya | sachin | | surya: अब तो पानी गिर रहा है!
- shot | sachin | coach | | sachin: कोच जी, भाषण बहुत लंबा था!
- face-off | coach | surya | बारिश | coach: मैच कल, भाषण बाकी है! // surya: कोच जी, भाषण ही रहने दो!

## Dadaji and Coach Duel | दादाजी और कोच
plot: Dadaji and Coach bet on who can catch better, and Dadaji wins sitting down while Golu counts.
ending: कुर्सी पर जीत पक्की!
hook: कैच की शर्त कौन जीता? 🥇
card: कैच की शर्त!
- face-off | dadaji | coach | शर्त | dadaji: कोच जी, कैच में मुझसे हारोगे! // coach: दादाजी, मैं दौड़कर पकड़ता हूँ!
- run-up | golu | sachin | | golu: दोनों में बड़ी शर्त लगी है!
- shot | sachin | coach | | sachin: कोच जी ने कैच गिरा दिया!
- catch | dadaji | coach | golu | dadaji: लो, कुर्सी पर बैठे पकड़ा! // coach: दादाजी, आप उस्ताद हो!

## Meena's Captain Day | मीना कप्तान
plot: Meena becomes captain for a day and makes Pappu field with a bucket on his head while Golu giggles.
ending: बाल्टी वाला फ़ील्डर!
hook: कप्तान मीना ने पप्पू को क्या सज़ा दी? 🪣
card: मीना कप्तान बनी!
- face-off | meena | pappu | कप्तान | meena: पप्पू भैया, सिर पर बाल्टी रखो!
- run-up | golu | sachin | | golu: अब तो बाल्टी वाला फ़ील्डर आया!
- shot | sachin | pappu | | sachin: पप्पू भैया, गेंद आ रही है!
- face-off | pappu | meena | बाल्टी | pappu: मीना, मेरी बाल्टी भारी है! // meena: कप्तान का हुक्म चलेगा!

## Meena's Secret Bat | मीना का बल्ला
plot: Meena hides her bat from the boys, and Sachin finds it in Aunty's kitchen where Aunty uses it as a rolling pin.
ending: बल्ला गया रसोई तक!
hook: मीना का बल्ला रसोई में कैसे पहुँचा? 🥖
card: मीना का बल्ला गुम!
- face-off | meena | sachin | बल्ला | meena: सचिन, मेरा बल्ला किसी को मत देना!
- run-up | surya | sachin | | surya: वो बल्ला रसोई में दिखा!
- shot | sachin | aunty | | sachin: आंटी, आप इससे क्या बेल रही हैं? // aunty: ये तो बढ़िया बेलन है!
- face-off | aunty | meena | बेलन | aunty: ये मेरा नया बेलन है! // meena: आंटी, ये मेरा बल्ला है!

## Meena Fixes the Score | मीना ने बताया
plot: Pintu counts the score wrongly, and Meena proves it with chalk marks while Golu keeps quiet.
ending: छत्तीस सही, चालीस ग़लत!
hook: स्कोर की गलती किसने पकड़ ली? 📝
card: स्कोर गलत गिना गया!
- face-off | pintu | meena | स्कोर | pintu: स्कोर चालीस है, मैंने गिना! // meena: पिंटू, ये चालीस नहीं है!
- run-up | golu | sachin | | golu: वो तो चाक लेकर आई है!
- shot | sachin | meena | | sachin: चाक से गिनती करके दिखा!
- face-off | meena | pintu | पोल | meena: देखो, ये तो छत्तीस निकला! // pintu: ओह, गिनती में मैं हार गया!

## Golu Spots It First | गोलू ने देखा
plot: Golu sees the ball going into Aunty's window before anyone else and shouts that he saw it, but it is already too late for Sachin.
ending: नज़र तेज़, किस्मत देर!
hook: गोलू ने गेंद को खिड़की में कैसे देखा? 👀
card: गोलू ने देखा!
- face-off | golu | sachin | खिड़की | golu: मैंने देखा, गेंद खिड़की में गई! // sachin: अब बता, गेंद कौन माँगेगा?
- run-up | sachin | golu | | sachin: गोलू, तू जाकर माँग ला!
- shot | golu | aunty | | aunty: ये गेंद मेरी खिड़की से आई!
- face-off | aunty | golu | माफ़ी | aunty: गोलू, पहले माफ़ी माँगो! // golu: आंटी, देर से देखा, माफ़ कर दो!

## Golu's Lucky Cap | गोलू की टोपी
plot: The cap is lucky only when Golu does not wear it, so the team keeps losing until Bruno wears it and Surya laughs.
ending: टोपी पहनी ब्रूनो ने!
hook: गोलू की लकी टोपी असल में किसकी निकली? 🧢
card: गोलू की लकी टोपी!
- face-off | golu | surya | टोपी | golu: मैंने टोपी पहनी और हम हार गए!
- run-up | surya | golu | | surya: टोपी उतार, किस्मत लौटेगी!
- shot | golu | bruno | | golu: ब्रूनो को टोपी पहनाकर देखते हैं!
- face-off | surya | bruno | जीत | surya: अब तो हम जीत गए! // bruno: भौं भौं!

## Golu Tiny Hero | छोटा हीरो
plot: Golu is too small to field, but a low catch comes to him and he holds it with two hands while Coach and Dadaji cheer.
ending: छोटा क़द, बड़ा हौसला!
hook: सबसे छोटे गोलू ने क्या कमाल किया? 🦸
card: छोटा हीरो गोलू!
- face-off | coach | golu | छोटा | coach: गोलू, तू तो बहुत छोटा है! // golu: कोच जी, मैं भी खेलूँगा!
- run-up | coach | sachin | | coach: ये गेंद नीची जाएगी!
- shot | sachin | golu | | sachin: गोलू के हाथ में गेंद आ गई!
- catch | dadaji | golu | coach | dadaji: शाबाश, छोटे हीरो! // golu: दादाजी, मैंने पकड़ लिया!

## Golu's Spy | गोलू का जासूस
plot: Golu tells Mintu and Pappu that the other gali is practicing in secret, but it turns out they are practicing a dance.
ending: मैदान में नाच चल रहा!
hook: दूसरी गली के राज़ में क्या निकला? 💃
card: दूसरी गली का राज़!
- face-off | golu | pappu | राज़ | golu: पप्पू भैया, उनकी गली में गुप्त अभ्यास है!
- run-up | mintu | golu | | mintu: मैं झाँककर देखता हूँ!
- shot | golu | mintu | | golu: उनके पास गेंद ही नहीं है!
- face-off | mintu | pappu | नाच | mintu: ये तो नाच की तैयारी है! // pappu: जासूस साहब ग़लत निकले!

## Pintu's Strict Day | पिंटू का सख़्त दिन
plot: Pintu gives everything wide, including a bird flying by, while Surya argues and Bruno watches.
ending: चिड़िया भी वाइड हो गई!
hook: पिंटू के सख़्त फ़ैसलों में क्या शामिल था? 🐤
card: पिंटू का सख़्त फ़ैसला!
- face-off | pintu | surya | वाइड | pintu: वाइड! ये भी वाइड, वो भी!
- run-up | surya | sachin | | surya: ये गेंद तो सीधी थी!
- shot | sachin | bruno | | sachin: एक चिड़िया भी बीच से निकली!
- face-off | surya | pintu | चिड़िया | surya: पिंटू, चिड़िया वाइड कैसे हुई? // pintu: उसने लाइन पार की!

## Pintu's Wrong Decision | पिंटू का फ़ैसला
plot: Pintu gives Sachin out, but Bruno's bark shows the ball hit Pintu's shoe, so Sachin is called back.
ending: जूते ने खोला राज़!
hook: पिंटू का फ़ैसला किसने पलटा? 👞
card: पिंटू का गलत फ़ैसला!
- face-off | pintu | sachin | आउट | pintu: सचिन, तू आउट है! // sachin: पिंटू, गेंद तो जूते पर लगी!
- run-up | surya | sachin | | surya: उसने तो मेरी गेंद खेली!
- shot | sachin | bruno | | sachin: ब्रूनो ने जूते की तरफ़ इशारा किया!
- face-off | pintu | sachin | जूता | pintu: ओह, जूते पर लगी थी! // sachin: अब तो मुझे वापस बुलाओ!

## Pintu vs Replay | पिंटू का रिप्ले
plot: Golu does a replay with a toy telescope and Pintu changes his decision while Sachin waits.
ending: खिलौना दूरबीन जीती!
hook: खिलौना दूरबीन देखकर पिंटू ने क्या किया? 🔭
card: खिलौने से रिप्ले!
- face-off | pintu | golu | रिप्ले | pintu: गोलू, ये दूरबीन क्यों लाया है? // golu: पिंटू भैया, रिप्ले दिखाऊँगा!
- run-up | golu | sachin | | golu: सचिन, फिर से गेंद मारना!
- shot | sachin | pintu | | sachin: पिंटू, अब बता, मैं आउट हूँ?
- face-off | pintu | golu | फ़ैसला | pintu: रिप्ले में तो नॉट आउट है! // golu: दूरबीन ने सच दिखा दिया!

## Aunty's Window Rule | आंटी की खिड़की
plot: Aunty puts up a sign that sixes are not allowed, but Surya hits a six anyway and the ball lands in her pot of laddoos while Bruno watches.
ending: मनाही तोड़ी, लड्डू मिले!
hook: आंटी की मनाही पर छक्का कहाँ गिरा? 🍬
card: आंटी की खिड़की!
- face-off | aunty | surya | मनाही | aunty: यहाँ छक्का मारना सख़्त मना है!
- run-up | sachin | surya | | sachin: सूर्या, इस बार ऊँचा मारना!
- shot | surya | bruno | | surya: ये लो छक्का, सीधा खिड़की में!
- face-off | aunty | surya | लड्डू | aunty: मेरे लड्डू के बर्तन में गिरा! // surya: आंटी, चलो गेंद के बदले लड्डू!

## Aunty Joins the Match | आंटी भी खेलीं
plot: Aunty takes the bat from Sachin for a moment, the next shot flies far, and she tells everyone she was only beating dough.
ending: आटे वाला शॉट!
hook: आंटी ने बल्ले से क्या कमाल दिखाया? 🏏
card: आंटी ने बल्ला उठाया!
- face-off | aunty | sachin | बल्ला | aunty: सचिन, ज़रा मुझे बल्ला दे दो!
- run-up | sachin | surya | | sachin: बड़े बल्लेबाज़ आए हैं, धीरे डालना!
- shot | surya | dadaji | | surya: वाह, शॉट आसमान में पहुँचा! // dadaji: ये किसका शॉट था?
- face-off | aunty | sachin | आटा | aunty: मैंने तो बस आटा गूँथा! // sachin: आंटी, आपने कमाल कर दिया!

## Aunty's Pakoras | आंटी के पकोड़े
plot: Aunty sends pakoras for the players, Golu and the others forget the match, and Bruno eats them all.
ending: थाली सफ़ाचट, खेल चटपट!
hook: पकोड़ों के चक्कर में मैच का क्या हुआ? 🥘
card: आंटी के पकोड़े!
- face-off | aunty | golu | पकोड़े | aunty: गोलू, ये गरम पकोड़े सबके लिए!
- run-up | golu | sachin | | golu: मैच बाद में, पहले खाना!
- shot | sachin | bruno | | sachin: अरे, थाली तो खाली हो गई!
- face-off | golu | bruno | थाली | golu: ब्रूनो ने सब खा लिए! // bruno: भौं भौं!

## Aunty's Cooker | आंटी का कुकर
plot: Aunty's cooker whistles at the exact moment of the last ball and Pintu stops the game while Surya complains.
ending: खाना तैयार, खेल बंद!
hook: आख़िरी गेंद पर किसने सीटी बजा दी? 🔔
card: आख़िरी गेंद पर सीटी!
- face-off | pintu | aunty | कुकर | pintu: आंटी, आपके कुकर ने सीटी बजा दी!
- run-up | surya | sachin | | surya: आख़िरी गेंद अब आ रही है!
- shot | sachin | pintu | | pintu: रुको, सीटी बजी है! // sachin: पिंटू, ये कुकर था!
- face-off | surya | aunty | सीटी | surya: आंटी, कुकर थोड़ी देर रुको! // aunty: बेटा, खाना भी तो चाहिए!

## Aunty's Biscuit Trade | आंटी की बिस्कुट
plot: Aunty trades a lost ball for a promise that Golu and Sachin will do homework first.
ending: पहले पढ़ाई, फिर खेल!
hook: होमवर्क का सौदा किसने किया? 📚
card: गेंद के बदले वादा!
- face-off | aunty | golu | सौदा | aunty: गेंद चाहिए तो पहले होमवर्क करो!
- run-up | sachin | golu | | sachin: गोलू, चल जल्दी से लिख लें!
- shot | golu | aunty | | golu: आंटी, देखिए मेरा काम पूरा है!
- face-off | aunty | sachin | वादा | aunty: ठीक है, अब गेंद मिलेगी! // sachin: आंटी, आप माँ जैसी हो!

## Pappu's Big Plan | पप्पू का प्लान
plot: Pappu makes a plan to win with a trick that needs a rope, a bucket and Bruno, and it falls apart in the first over while Sachin watches.
ending: प्लान फेल, पप्पू गीला!
hook: पप्पू के बड़े प्लान का क्या हुआ? 🪢
card: पप्पू का बड़ा प्लान!
- face-off | pappu | sachin | प्लान | pappu: आज मेरा प्लान पक्का जीतेगा!
- run-up | pappu | sachin | | pappu: रस्सी खींचो, बाल्टी तैयार रखो!
- shot | sachin | bruno | | sachin: ब्रूनो रस्सी में उलझ गया!
- face-off | sachin | pappu | बाल्टी | sachin: बाल्टी तो तुम्हारे सिर पर गिरी! // pappu: पहले ही ओवर में प्लान गया!

## Pappu Becomes Captain | पप्पू कप्तान
plot: Pappu becomes captain and gives himself the easiest job of a fielder who never moves, while Coach and Meena watch.
ending: कप्तान खड़ा, टीम परेशान!
hook: कप्तान पप्पू ने खुद को कौन सी जगह दी? 🪑
card: पप्पू बना कप्तान!
- face-off | pappu | coach | कप्तान | pappu: आज मैं कप्तान हूँ, सब सुनो!
- run-up | meena | pappu | | meena: पप्पू भैया, आप कहाँ खड़े होंगे?
- shot | pappu | meena | | pappu: मैं यहीं खड़ा रहूँगा, हिलूँगा नहीं!
- face-off | coach | pappu | जगह | coach: ये कैसी फ़ील्डिंग है? // pappu: कप्तान की मर्ज़ी है!

## Pappu's Excuse | पप्पू का बहाना
plot: Pappu is out and says the sun was in his eyes, but it was already night, and Pintu and Dadaji laugh.
ending: रात में धूप निकली!
hook: पप्पू ने आउट होने का क्या बहाना बनाया? 🌞
card: पप्पू का बहाना!
- face-off | pintu | pappu | बहाना | pintu: पप्पू, तू आउट है, जा बैठ!
- run-up | sachin | pappu | | pappu: धूप आँखों में लग रही थी!
- shot | pappu | dadaji | | dadaji: बेटा, अभी तो रात हो चुकी है!
- face-off | pintu | dadaji | अँधेरा | pintu: दादाजी, रात में धूप कैसे निकली? // dadaji: बहाने की रात में!

## Chhotu Weighs the Ball | छोटू का वज़न
plot: Chhotu can tell by weight that the ball has been swapped, and the team checks and finds Mintu's ball while Surya looks on.
ending: तराज़ू ने पकड़ा बेईमान!
hook: छोटू ने गेंद का वज़न देखकर क्या पकड़ा? ⚖
card: छोटू की तराज़ू!
- face-off | chhotu | mintu | वज़न | chhotu: ये गेंद तो हल्की निकली, मिंटू!
- run-up | surya | chhotu | | surya: छोटू, वज़न कैसे पता चला?
- shot | chhotu | surya | | chhotu: दुकान में रोज़ तौलता हूँ!
- face-off | mintu | chhotu | बदली | mintu: मैंने गेंद बदल दी थी! // chhotu: बेईमानी नहीं चलेगी, मिंटू!

## Chhotu's Shop Match | छोटू की दुकान
plot: The match moves to the shop lane, and Sachin's ball knocks down a pyramid of cans, so Chhotu and Golu rebuild it together.
ending: डिब्बों का ढेर फिर खड़ा!
hook: दुकान की गली में गेंद ने क्या गिरा दिया? 🥫
card: छोटू की दुकान में मैच!
- face-off | chhotu | sachin | डिब्बे | chhotu: सचिन, मेरे डिब्बे गिर गए!
- run-up | golu | sachin | | golu: चलो, पहले डिब्बे दोबारा लगाएँ!
- shot | sachin | chhotu | | sachin: माफ़ करना, गेंद उधर चली गई!
- face-off | chhotu | golu | ढेर | chhotu: अब सब मिलकर ढेर लगाओ! // golu: ठीक है, छोटू भैया!

## Chhotu's New Bat | छोटू का नया बल्ला
plot: Chhotu tells Pappu and Surya that he has a new bat for them, but it is the same old bat with a ribbon.
ending: रिबन बाँधा, बल्ला बेचा!
hook: छोटू का नया बल्ला असल में क्या था? 🎀
card: छोटू का नया बल्ला!
- face-off | chhotu | pappu | बल्ला | chhotu: पप्पू भैया, ये नया बल्ला आया है!
- run-up | surya | pappu | | surya: ये तो वही पुराना बल्ला लग रहा!
- shot | pappu | chhotu | | pappu: इस पर तो बस रिबन बँधा है!
- face-off | chhotu | surya | रिबन | chhotu: रिबन भी तो नया है! // surya: छोटू, तू तो चालाक निकला!

## Mintu's Trick | मिंटू की चाल
plot: Mintu hides a second ball to win, two balls come in the same over, and Pintu is confused while Bruno watches.
ending: दो गेंदें, एक उलझन!
hook: एक ओवर में दो गेंदें कैसे आ गईं? 🎱
card: मिंटू की गुप्त चाल!
- face-off | mintu | pintu | चाल | mintu: पिंटू भैया, गेंद एक ही है!
- run-up | mintu | sachin | | mintu: दूसरी गेंद भी आ रही है!
- shot | sachin | bruno | | sachin: दो-दो गेंदें, मैं किसे खेलूँ?
- face-off | pintu | mintu | उलझन | pintu: ये दो गेंदें कहाँ से आईं? // mintu: मुझे तो पता ही नहीं!

## Mintu Caught | मिंटू पकड़ा गया
plot: Mintu spies on the gali, and Bruno finds him hiding inside a drum while Pappu laughs.
ending: ड्रम में जासूस पकड़ा!
hook: ड्रम में छुपा जासूस कौन निकला? 🛢
card: ड्रम में कौन है?
- face-off | pappu | bruno | ड्रम | pappu: ब्रूनो, उस ड्रम में कोई है!
- run-up | surya | sachin | | surya: कोई हमारी बातें सुन रहा है!
- shot | sachin | mintu | | sachin: मिंटू, तू ड्रम में क्या कर रहा है?
- face-off | mintu | pappu | पोल | mintu: मैं तो बस खेल देख रहा था! // pappu: ड्रम में बैठकर खेल देखा?

## Mintu Joins | मिंटू मान गया
plot: Mintu loses the match and finally says sorry, and the gali invites him to play with Sachin and Meena.
ending: माफ़ी माँगी, दोस्त बना!
hook: मिंटू हारकर दोस्त कैसे बना? 🤝
card: मिंटू ने माफ़ी माँगी!
- face-off | mintu | sachin | माफ़ी | mintu: सचिन, मैं हार गया, माफ़ करो!
- run-up | meena | mintu | | meena: चलो, अब तुम भी खेलो!
- shot | mintu | sachin | | mintu: आज पहली बार मज़ा आया!
- face-off | sachin | meena | दोस्ती | sachin: अब ये भी हमारी टीम में! // meena: बहुत बढ़िया फ़ैसला!

## Sachin One More Six | सचिन का एक और छक्का
plot: Sachin says one more six and that is all four times, and finally falls asleep on the pitch while Dadaji and Bruno watch.
ending: नींद जीती, सचिन सोया!
hook: सचिन का एक और छक्का कहाँ अटका? 😴
card: बस एक और छक्का!
- face-off | sachin | dadaji | छक्का | sachin: बस एक और छक्का, फिर बंद!
- run-up | surya | sachin | | surya: चौथी बार वही रट लगा रहा!
- shot | sachin | bruno | | sachin: ये आख़िरी, बिल्कुल आख़िरी छक्का!
- face-off | dadaji | sachin | नींद | dadaji: अरे, ये तो पिच पर सो गया!

## Sachin's Sleepy Catch | सचिन की नींद
plot: Sachin dozes in the outfield and the ball falls into his hands, so he wakes up a hero while Coach and Surya cheer.
ending: ऊँघता सचिन बना शेर!
hook: ऊँघते सचिन के हाथ में क्या आ गिरा? 💤
card: सचिन की नींद!
- face-off | coach | sachin | नींद | coach: सचिन, सो मत, गेंद आ रही है!
- run-up | surya | sachin | | surya: ये ऊँचा शॉट ख़तरनाक है!
- shot | sachin | surya | | sachin: अरे, गेंद मेरे हाथ में आई!
- face-off | coach | sachin | हीरो | coach: नींद में भी कैच पकड़ लिया! // sachin: कोच जी, ये तो इत्तेफ़ाक है!

## Sachin vs Surya | सचिन बनाम सूर्या
plot: Surya says it was his ball and Sachin says it was his shot, and they both lose it to Bruno.
ending: दोनों झगड़ते रहे, ब्रूनो भागा!
hook: गेंद के झगड़े में असली जीत किसकी हुई? 🐕
card: गेंद किसकी थी?
- face-off | surya | sachin | झगड़ा | surya: ये मेरी गेंद थी, मैंने डाली!
- run-up | surya | sachin | | sachin: नहीं, मैंने शॉट मारा था!
- shot | sachin | bruno | | sachin: देखो, कुत्ता गेंद दबाए भाग रहा!
- face-off | surya | bruno | भागा | surya: वापस आ, हमारी गेंद लौटा!

## Surya Says Sorry | सूर्या ने माफ़ी माँगी
plot: Surya breaks Aunty's pot, says sorry with a pakora, and the gali plays on while Bruno wags his tail.
ending: पकोड़े की माफ़ी मंज़ूर!
hook: सूर्या ने आंटी को माफ़ी में क्या दिया? 🥟
card: सूर्या का सॉरी!
- face-off | aunty | surya | गमला | aunty: सूर्या, मेरा गमला तूने तोड़ दिया!
- run-up | sachin | surya | | sachin: जल्दी से कुछ करके माफ़ी माँग!
- shot | surya | aunty | | surya: आंटी, ये गरम पकोड़ा लीजिए, सॉरी!
- face-off | aunty | bruno | पकोड़ा | aunty: चलो, इस बार माफ़ किया! // bruno: भौं भौं!

## Sankranti Kite and Ball | संक्रांति की पतंग
plot: A kite and a ball collide above the gali, and both land in Dadaji's hands while Golu and Mintu cheer.
ending: आसमान से सीधी झोली!
hook: आसमान में पतंग और गेंद टकराई तो क्या हुआ? 🪁
card: आसमान में टक्कर!
- face-off | golu | mintu | पतंग | golu: मिंटू, पतंग और गेंद टकरा गईं!
- run-up | mintu | golu | | mintu: ऊपर देखो, दोनों नीचे आ रही हैं!
- shot | golu | dadaji | | golu: दादाजी, ऊपर देखो, कुछ गिर रहा है!
- catch | dadaji | golu | mintu | dadaji: पतंग भी मेरी, गेंद भी मेरी! // golu: दादाजी, आपका तो डबल धमाका!

## Diwali Lamps | दिवाली के दिए
plot: The team plays near rows of lamps and Surya bowls softly so Sachin can bat without breaking a single one, while Aunty watches over them.
ending: दीये बचे, छक्के रुके!
hook: दीयों के बीच क्रिकेट कैसे खेला गया? 🪔
card: दीयों के बीच मैच!
- face-off | aunty | sachin | दीये | aunty: सचिन, मेरे दीये मत तोड़ना!
- run-up | surya | sachin | | surya: संभलकर, गेंद धीरे आ रही है!
- shot | sachin | aunty | | sachin: आंटी, मैंने सिर्फ़ हल्का शॉट मारा!
- face-off | aunty | surya | रोशनी | aunty: सब दीये सलामत हैं! // surya: आंटी, आज मैच जगमग रहा!

## Raksha Bandhan Match | राखी का मैच
plot: Meena ties a rakhi on Surya's wrist, and Surya cannot bowl fast to his sister while Bruno waits.
ending: राखी बँधी, गेंद धीमी!
hook: बहन को देखकर सूर्या की गेंद क्यों रुकी? 🧵
card: राखी बँधी, मैच रुका!
- face-off | meena | surya | राखी | meena: सूर्या, आज तेरी कलाई पर राखी बँधेगी!
- run-up | surya | meena | | surya: बहन को तेज़ गेंद कैसे डालूँ?
- shot | meena | bruno | | meena: धीमी गेंद पर छक्का तो पक्का!
- face-off | surya | meena | भाई | surya: अब मैं सिर्फ़ धीमी गेंद डालूँगा! // meena: बहन के लिए इतनी मेहरबानी!

## Mela Day | मेले का दिन
plot: The match is played between two stalls at the fair, and the ball lands on a balloon seller while Chhotu and Pappu run after it.
ending: गुब्बारे फूटे, मेला जमा!
hook: गुब्बारे वाला मैच के बीच में क्यों आया? 🎈
card: मेले में मैच!
- face-off | chhotu | pappu | मेला | chhotu: पप्पू भैया, मेले में मैच खेलेंगे!
- run-up | pappu | chhotu | | pappu: दो दुकानों के बीच गेंद फेंकता हूँ!
- shot | chhotu | bruno | | chhotu: अरे, गेंद गुब्बारे वाले पर गिरी!
- face-off | pappu | chhotu | गुब्बारा | pappu: सारे गुब्बारे फूट गए! // chhotu: अब पैसे हमें देने पड़ेंगे!

## Monsoon Pitch | बरसात की पिच
plot: The pitch is a puddle, the ball does not bounce, and Sachin, Surya and Golu turn the game into a boat race.
ending: गेंद तैरी, पिच डूबी!
hook: पानी भरी पिच पर मैच कैसे हुआ? ⛵
card: पिच बनी तालाब!
- face-off | sachin | surya | पानी | sachin: पिच तो पूरी तालाब बन गई!
- run-up | surya | golu | | surya: गेंद तो पानी में तैर रही है!
- shot | golu | sachin | | golu: अब नाव की रेस लगाते हैं!
- face-off | sachin | surya | नाव | sachin: ये मैच तो नाव बन गया! // surya: कागज़ की नाव सबसे आगे!

## Summer Afternoon | गर्मी की दोपहर
plot: It is too hot so everyone plays under the neem tree, and the ball keeps hitting Dadaji's nap while Golu and Pintu giggle.
ending: नीम की छाँव मज़ेदार!
hook: नीम की छाँव में दादाजी की नींद किसने तोड़ी? 🌳
card: गर्मी की दोपहर!
- face-off | golu | pintu | गर्मी | golu: पिंटू भैया, आज बहुत गर्मी है!
- run-up | golu | sachin | | golu: चलो, नीम के नीचे खेलते हैं!
- shot | sachin | dadaji | | sachin: गेंद दादाजी की गोद में गिरी!
- face-off | dadaji | pintu | नींद | dadaji: कौन है जो मेरी नींद तोड़ रहा है? // pintu: दादाजी, ये तो गेंद का काम है!

## Winter Morning | सर्दी की सुबह
plot: Sachin and Meena play in blankets and the bat is the hardest thing to hold, while Aunty brings hot tea.
ending: कंबल में क्रिकेट, ठिठुरन!
hook: सर्दी की सुबह कंबल में क्रिकेट कैसे हुआ? 🧣
card: सर्दी में कंबल क्रिकेट!
- face-off | sachin | meena | सर्दी | sachin: मीना, मेरा बल्ला पकड़ ही नहीं आता!
- run-up | meena | sachin | | meena: कंबल में हाथ फँस गए!
- shot | sachin | aunty | | aunty: ठंड में भी मैच नहीं छोड़ते!
- face-off | aunty | meena | चाय | aunty: लो, ये गरम चाय पी लो! // meena: आंटी, अब हाथ में जान आई!

## Exam Week Match | परीक्षा के दिन
plot: Golu and Sachin play only in the one gap between two exam papers, and every ball is counted as revision while Aunty watches.
ending: हर गेंद पर पढ़ाई!
hook: परीक्षा के बीच खेल का वक़्त कैसे निकला? 📖
card: परीक्षा के बीच मैच!
- face-off | golu | sachin | परीक्षा | golu: सचिन, आज दो घंटे का गैप है!
- run-up | sachin | golu | | sachin: हर गेंद पर एक सवाल!
- shot | golu | aunty | | golu: आंटी, ये रिवीज़न का शॉट था!
- face-off | aunty | sachin | किताब | aunty: अब सब किताब पढ़ो, खेल खत्म! // sachin: आंटी, एक और गेंद!

## Power Cut Match | बिजली गई, मैच चला
plot: Everyone plays with torches and Aunty's lantern, and Bruno's collar and the lantern become the floodlights while Pintu umpires.
ending: बिजली गई, लालटेन जली!
hook: बिजली जाने पर मैच कैसे चला? 🔦
card: टॉर्च से मैच!
- face-off | aunty | pintu | लालटेन | aunty: पिंटू, मेरी लालटेन ऊपर टाँग दो!
- run-up | surya | sachin | | surya: टॉर्च की रोशनी में गेंद आई!
- shot | sachin | bruno | | sachin: ब्रूनो की पट्टी भी चमक रही है!
- face-off | pintu | aunty | फ़्लड | pintu: ये तो पूरा स्टेडियम बन गया! // aunty: मेरी लालटेन सबसे चमकदार!

## Wedding Gali | शादी की गली
plot: A baraat is coming and the wedding lights cover the gali, and the ball flies while Pappu and Dadaji dare not look at the groom.
ending: बारात आई, छक्का छुपा!
hook: बारात की रोशनी में छक्का कहाँ गया? 💒
card: शादी की गली में मैच!
- face-off | pappu | dadaji | बारात | pappu: दादाजी, बारात इसी गली से आ रही है!
- run-up | sachin | pappu | | sachin: जल्दी करो, आख़िरी गेंद!
- shot | pappu | bruno | | pappu: ये छक्का सीधा दूल्हे की तरफ़ गया!
- face-off | dadaji | pappu | दूल्हा | dadaji: अब कोई दूल्हे की तरफ़ मत देखना!

## New Neighbour | नया पड़ोसी
plot: A new boy joins the match and hits the first ball over everyone, so Sachin, Meena and Coach make him a friend.
ending: नया छक्का, नया दोस्त!
hook: नया पड़ोसी पहली गेंद पर क्या कर गया? 🏘
card: नया लड़का आया!
- face-off | sachin | meena | पड़ोसी | sachin: मीना, ये नया लड़का कौन है?
- run-up | meena | sachin | | meena: चलो, इसे भी खिला लेते हैं!
- shot | sachin | coach | | sachin: पहली गेंद पर ही छक्का मार दिया!
- face-off | coach | meena | दोस्ती | coach: शाबाश, अब यह हमारा साथी! // meena: कोच जी, बिल्कुल सही!

## Old Ball Retires | पुरानी गेंद
plot: The old ball is worn out, so Dadaji and Golu give it a farewell while Chhotu brings a new ball from his shop.
ending: नई गेंद, नया जोश!
hook: पुरानी गेंद की विदाई कैसे हुई? 🎊
card: पुरानी गेंद की विदाई!
- face-off | dadaji | golu | विदाई | dadaji: गोलू, ये पुरानी गेंद अब थक गई!
- run-up | golu | sachin | | golu: इसे विदाई देकर नई लेते हैं!
- shot | sachin | chhotu | | sachin: छोटू, तेरी दुकान से नई गेंद लाया?
- face-off | chhotu | dadaji | सलाम | chhotu: ये रही बिल्कुल नई गेंद! // dadaji: पुरानी गेंद, तुझे सलाम!

## Meerut Market Match | बाज़ार का मैच
plot: The match goes through the Abu Lane market, and Sachin's ball bounces between shops while each shopkeeper shouts out or four, with Chhotu and Pintu leading the fun.
ending: दुकानदारों की अपनी बाज़ी!
hook: अबू लेन में मैच हुआ तो दुकानदार क्या बने? 🏬
card: बाज़ार में क्रिकेट!
- face-off | chhotu | pintu | बाज़ार | chhotu: पिंटू भैया, आज बाज़ार में मैच है!
- run-up | chhotu | sachin | | sachin: गेंद दुकानों से टकराकर लौट आई!
- shot | sachin | bruno | | sachin: दुकानदार चिल्ला रहे, चौका, आउट, चौका!
- face-off | chhotu | pintu | अंपायर | chhotu: यहाँ हर दुकानदार अंपायर है! // pintu: ये तो मेरठ का मैच है!

## Last Ball of the Day | दिन की आख़िरी गेंद
plot: The sun sets, everyone is tired, Dadaji says one more, and the last ball lands in his hands while Sachin and Surya cheer.
ending: शाम ढली, मैच मुकम्मल!
hook: दिन की आख़िरी गेंद किसके हाथ में गई? 🌇
card: दिन की आख़िरी गेंद!
- face-off | dadaji | sachin | शाम | dadaji: बस एक और गेंद, फिर घर!
- run-up | surya | sachin | | surya: धूप ढल रही है, जल्दी करो!
- shot | sachin | bruno | | sachin: ये लो आख़िरी शॉट!
- catch | dadaji | sachin | surya | dadaji: लो, आख़िरी गेंद भी मेरी! // sachin: दादाजी, आख़िरी कैच भी आपका!

## Bruno the Referee | ब्रूनो रेफरी
plot: Mintu and Meena fight over a boundary, and Bruno drops the ball exactly on the line so everyone sees the truth.
ending: लाइन पर इंसाफ़ हुआ!
hook: बाउंड्री के झगड़े का फ़ैसला किसने किया? 🧐
card: सीमा का झगड़ा!
- face-off | mintu | meena | सीमा | mintu: ये गेंद सीमा के अंदर गिरी! // meena: नहीं, बाहर गिरी थी!
- run-up | mintu | meena | | meena: ठीक है, फिर से डालो!
- shot | meena | bruno | | meena: ब्रूनो, तू ही फ़ैसला कर!
- face-off | bruno | mintu | लाइन | mintu: कुत्ते ने गेंद ठीक लाइन पर रखी!

## Bruno vs Monkey | ब्रूनो बनाम बंदर
plot: A monkey grabs the ball, and Bruno chases it over three roofs and returns with the ball and one banana while Golu and Aunty cheer.
ending: गेंद लौटी, केला बोनस!
hook: बंदर से गेंद वापस कौन लाया? 🐒
card: बंदर गेंद ले गया!
- face-off | golu | aunty | बंदर | golu: आंटी, बंदर हमारी गेंद ले गया!
- run-up | golu | sachin | | sachin: बंदर तीन छतें कूद गया!
- shot | golu | bruno | | golu: ब्रूनो गेंद के साथ केला भी लाया!
- face-off | aunty | golu | केला | aunty: ये केला किसका है? // golu: आंटी, ये बहादुरी का तोहफ़ा है!

## Bruno's Big Six | ब्रूनो का छक्का
plot: The ball hits Bruno's back and bounces over the wall, Pintu signals a six, and Sachin says Bruno takes a bow.
ending: पीठ का छक्का, ग़ज़ब!
hook: ब्रूनो की पीठ से छक्का कैसे बना? 🏏
card: पीठ से छक्का!
- face-off | sachin | bruno | पीठ | sachin: गेंद ब्रूनो की पीठ से टकराई!
- run-up | surya | sachin | | surya: अब ये गेंद देखो!
- shot | sachin | pintu | | sachin: सीधी दीवार के उस पार! // pintu: छह रन, पूरा छक्का!
- face-off | pintu | bruno | झुकना | pintu: ये तो ब्रूनो का छक्का है!

## Bruno Misses the Match | ब्रूनो नहीं आया
plot: Everyone plays badly without Bruno, and Coach and Pappu find him asleep on his favourite spot of the pitch and decide to play around him.
ending: सोता ब्रूनो, घूमता मैच!
hook: ब्रूनो के बिना मैच का क्या हुआ? 😪
card: ब्रूनो कहाँ है?
- face-off | coach | pappu | ग़ायब | coach: आज हमारा खिलाड़ी ग़ायब है!
- run-up | pappu | sachin | | pappu: आज सबका खेल बिगड़ा है!
- shot | sachin | bruno | | sachin: ब्रूनो तो पिच पर सो रहा है!
- face-off | coach | pappu | नींद | coach: इसी के चारों तरफ़ खेलो! // pappu: कोच जी, आज यही पिच है!

## Bruno at the Wedding Band | ब्रूनो और बैंड
plot: A baraat band passes, Bruno follows the drum with the ball, and the groom's party ends up playing gali cricket with Pappu and Dadaji.
ending: शहनाई में चौका!
hook: ढोल के पीछे ब्रूनो गेंद लेकर कहाँ गया? 🥁
card: बैंड वाला मैच!
- face-off | pappu | dadaji | बैंड | pappu: दादाजी, बारात का बैंड आ गया!
- run-up | sachin | surya | | sachin: ढोल की आवाज़ पर गेंद आई!
- shot | surya | bruno | | surya: ब्रूनो ढोल के पीछे भाग गया!
- face-off | dadaji | pappu | बाराती | dadaji: बाराती भी बल्ला उठा लाए! // pappu: गली में शादी का मैच!

## Bruno Counts Overs | ब्रूनो गिने ओवर
plot: Golu counts the balls wrongly, and Pintu and Sachin trust Bruno who barks exactly six times in every over.
ending: छह भौंक, एक ओवर!
hook: ओवर की गिनती किसने सही की? 🔔
card: ब्रूनो गिनता है!
- face-off | golu | pintu | ओवर | golu: ये तो सातवीं गेंद है!
- run-up | golu | sachin | | sachin: नहीं गोलू, अभी छठी है!
- shot | sachin | bruno | | sachin: ब्रूनो ने छह बार आवाज़ दी!
- face-off | pintu | golu | गिनती | pintu: अब उसकी गिनती सही! // golu: मुझसे बेहतर गिनता है!

## Bruno the Night Guard | ब्रूनो रात का पहरेदार
plot: A cat steals the ball at night, and Bruno stays awake and wins it back by morning while Dadaji praises him.
ending: रात भर जागा पहरेदार!
hook: रात में बिल्ली ने गेंद कहाँ छुपाई? 🐈
card: बिल्ली गेंद ले गई!
- face-off | dadaji | bruno | रात | dadaji: ब्रूनो, बिल्ली गेंद ले गई!
- run-up | golu | sachin | | golu: रात भर कोई जागता रहा!
- shot | sachin | bruno | | sachin: ब्रूनो की आँखें कितनी लाल हैं!
- face-off | dadaji | bruno | सुबह | dadaji: गेंद वापस आ गई, शाबाश!

## Bruno vs the Broom | ब्रूनो और झाड़ू
plot: Aunty sweeps and Bruno thinks the broom is the enemy, and the broom sends the ball flying into Dadaji's catch.
ending: झाड़ू बनी खिलाड़ी!
hook: झाड़ू लगी तो गेंद कहाँ उड़ गई? 🧹
card: झाड़ू से गेंद उड़ी!
- face-off | aunty | bruno | झाड़ू | aunty: ब्रूनो, झाड़ू से मत डर!
- run-up | sachin | surya | | sachin: गेंद आँगन में चली गई!
- shot | surya | aunty | | aunty: मेरी झाड़ू से गेंद उछल गई!
- catch | dadaji | bruno | aunty | dadaji: उछली गेंद सीधी मेरे हाथ में! // aunty: दादाजी, झाड़ू ने कैच दिया!

## Bruno Picks the Winner | ब्रूनो ने जिताया
plot: The match is tied, both captains Pappu and Mintu give Bruno a biscuit, and he drops the ball into the team that gave the bigger one.
ending: बिस्कुट ने तय किया फ़ैसला!
hook: बराबरी का मैच ब्रूनो ने कैसे जिताया? 🍪
card: बराबर मैच, ब्रूनो जज!
- face-off | pappu | mintu | बराबरी | pappu: मैच बराबर है, मैं नहीं हारूँगा!
- run-up | pappu | mintu | | mintu: ये लो बिस्कुट, इधर आओ!
- shot | mintu | bruno | | mintu: मेरा बिस्कुट बड़ा है, देख!
- face-off | pappu | bruno | जीत | pappu: ये बिस्कुट बड़ा है, इधर आ!

## Bruno Hears the Ice-cream Bell | ब्रूनो और कुल्फ़ी
plot: The kulfi bell rings and Golu and the whole team run, but Bruno stays and guards the pitch, and Chhotu rewards him with an ice cream.
ending: वफ़ादार ब्रूनो, ठंडा तोहफ़ा!
hook: घंटी सुनकर ब्रूनो पहरे पर क्यों रहा? 🍦
card: कुल्फ़ी की घंटी!
- face-off | golu | chhotu | कुल्फ़ी | golu: कुल्फ़ी वाले की घंटी बजी, दौड़ो!
- run-up | chhotu | golu | | chhotu: सब चले गए, पिच अकेली है!
- shot | golu | bruno | | golu: ब्रूनो पिच की रखवाली कर रहा है!
- face-off | chhotu | bruno | इनाम | chhotu: चल, तुझे भी आइसक्रीम दिलाऊँ!

## Bruno Files Paw Prints | ब्रूनो फ़ाइल्स: अनजान पंजे
plot: Golu's ball vanishes from the gali every night, and Bruno sniffs out paw prints that are not his own while Sachin watches.
ending: शक पक्का, सबूत कच्चा!
hook: रात में गली से गेंद कौन ले जाता है? 🐾
card: गेंद फिर गायब!
series: Bruno Files
ep: 1
- face-off | golu | sachin | गायब | golu: मेरी गेंद रात में फिर गायब! // sachin: तीसरी बार हुआ है!
- run-up | sachin | golu | | sachin: आज जासूसी शुरू करते हैं!
- shot | golu | bruno | | golu: ब्रूनो, ये पंजे तेरे नहीं हैं!
- face-off | sachin | bruno | सुराग | sachin: तो ये पंजे किसके हैं?

## Bruno Files Bell Trap | ब्रूनो फ़ाइल्स: घंटी का जाल
plot: Meena and Golu tie a bell to a new ball as a trap, the bell rings at night, and in the morning Bruno finds only a black feather.
ending: जाल बजा, चोर उड़ा!
hook: घंटी वाले जाल में सुबह क्या मिला? 🪤
card: घंटी का जाल!
series: Bruno Files
ep: 2
- face-off | meena | golu | जाल | meena: गेंद पर घंटी बाँध दी है! // golu: अब चोर पकड़ा जाएगा!
- run-up | golu | meena | | golu: रात में घंटी बजी थी!
- shot | meena | bruno | | meena: ब्रूनो को सिर्फ़ एक काला पंख मिला!
- face-off | golu | bruno | पंख | golu: क्या हमारा चोर उड़ता है?

## Bruno Files Tank Thief | ब्रूनो फ़ाइल्स: टंकी वाला चोर
plot: Bruno leads Sachin and Dadaji to the water tank, where a crow has been hiding every lost ball, and the gali gets all its balls back.
ending: कौआ पकड़ा, गेंदें लौटीं!
hook: गली की गेंदें आख़िर कौन चुराता था? 🪶
card: चोर मिल गया!
series: Bruno Files
ep: 3
- face-off | sachin | bruno | टंकी | sachin: ब्रूनो टंकी की तरफ़ भौंक रहा है!
- run-up | sachin | golu | | golu: ऊपर एक कौआ बैठा है!
- shot | golu | dadaji | | dadaji: अरे, यहाँ तो सारी गेंदें रखी हैं!
- catch | dadaji | sachin | bruno | dadaji: लो, सारी गेंदें वापस! // sachin: ब्रूनो, अगला केस क्या है?
