# Infoniss: मीटिंग और मोशन ग्राफ़िक्स का काम, फ़ोन से

यह repository आपका workspace है। फ़ोन के Claude app में बस लिखकर बताइए कि क्या चाहिए।
काम Claude करेगा, तैयार फ़ाइल app में दिखा देगा, और सब कुछ यहीं GitHub पर save कर देगा।

## फ़ोन से काम कैसे करें

1. Claude app में **Code** खोलें और नया session शुरू करें।
2. Repository में `infonisseditingstyleand-motion-graphics` चुनें।
3. हिंदी में लिख दीजिए क्या चाहिए। तैयार video या फ़ाइल app में ही खुल जाएगी।

## मीटिंग वाले काम: ऐसे लिखें

- "कल शाम 5 बजे क्लाइंट मीटिंग का एजेंडा बनाओ, मुद्दे: बजट, डेडलाइन, नया प्रोजेक्ट"
- "ये मीटिंग के नोट्स हैं (नोट्स paste करें), इनसे MoM बनाओ और किसको क्या करना है उसकी लिस्ट"
- "मीटिंग के बाद क्लाइंट को भेजने के लिए WhatsApp मैसेज लिखो"
- "अगले सोमवार 11 बजे Google Calendar में मीटिंग डालो"
  (Google Calendar जुड़ा हो तो। Event बनाने या email भेजने से पहले Claude आपसे पूछेगा।)

हर मीटिंग की फ़ाइल `meetings/` फ़ोल्डर में तारीख के नाम से save होती है।

## मोशन ग्राफ़िक्स: ऐसे लिखें

- "मेरा lower third बनाओ: नाम Infoniss, नीचे 'वीडियो एडिटर' लिखा हो, रंग नीला"
- "Reel के लिए title intro बनाओ: 'आज की एडिटिंग टिप'"
- "ये lower third green screen में दो, CapCut में लगाना है"
- "नया template बनाओ: subscribe बटन वाली end screen"

### कौन सा format माँगें

| आप कहाँ एडिट करते हैं | क्या माँगें |
|---|---|
| फ़ोन पर (CapCut, KineMaster, VN) | **green screen** वाला MP4, फिर app में *Chroma Key* लगाएँ |
| कंप्यूटर पर (Premiere, After Effects, DaVinci, Final Cut) | **transparent (alpha)** .mov |
| सीधे पोस्ट करना है | normal MP4: **reel** (9:16), **16:9** या **square** |

### अभी के templates

| Template | क्या है | Demo video |
|---|---|---|
| `lower-third` | नाम और पद वाली पट्टी (interview, talking head) | `motion-graphics/output/lower-third.mp4`, `lower-third-green.mp4` |
| `title-reveal` | intro या chapter title, शब्द-दर-शब्द animation | `motion-graphics/output/title-reveal.mp4`, `title-reveal-reel.mp4` |

हर template में text और रंग बदले जा सकते हैं। नए template भी बनवा सकते हैं।

## फ़ोल्डर

```
meetings/
  templates/        एजेंडा और MoM के खाके
  YYYY-MM-DD-*.md   हर मीटिंग की फ़ाइल
motion-graphics/
  templates/        animation templates (HTML)
  output/           तैयार videos
  assets/           font (Hindi + English) और helper
  render.js         template से video बनाने वाला tool
```
