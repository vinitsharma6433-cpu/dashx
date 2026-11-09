# Dialogue story bank (the cartoon format)

Every spoken line is said by one character, in the first person, in that character's own voice (voices.json).
No narration: no "X बोला", no "X ने कहा". The narrator only reads the end card.

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
