console.log('Starting function initialization');

const { onRequest } = require('firebase-functions/v2/https');
const axios = require('axios');
const cors = require('cors')({ origin: true });

console.log('Modules loaded successfully');

exports.describeimage = onRequest(
  {
    timeoutSeconds: 120,
    memory: '256MB',
    region: 'us-central1',
    invoker: 'public',
    secrets: ["GEMINI_API_KEY"],
  },
  async (req, res) => {
    cors(req, res, async () => {
      console.log('describeimage (onRequest) invoked with body:', JSON.stringify(req.body));
      const imageUrl = req.body.data?.imageUrl;
      if (!imageUrl) {
        console.error('Missing imageUrl in req.body.data');
        res.status(400).send({ error: { message: 'Invalid argument: Missing imageUrl in the request body.' } });
        return;
      }
      try {
        console.log('Fetching image from:', imageUrl);
        const imageResponse = await axios.get(imageUrl, { responseType: 'arraybuffer' });
        console.log('Image fetched, converting to base64');
        const base64Image = Buffer.from(imageResponse.data, 'binary').toString('base64');
        if (!process.env.GEMINI_API_KEY) {
            console.error('GEMINI_API_KEY not found in environment.');
            throw new Error('Server configuration error: API key is missing.');
        }

        console.log('Calling Gemini API with gemini-1.5-flash model and analyst prompt...');
        const geminiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${process.env.GEMINI_API_KEY}`;
        
        const geminiResponse = await axios.post(
          geminiUrl,
          {
            contents: [{
              parts: [
                { text: "Please give a solid analysis of the day's news, based on this newspaper front page. Go through the headlines, the stories, what is says about the current state of politics, the public mood etc. Be creative. Start with \"Today's insert newspaper title here front page...\" - this must be how it starts." },
                { inlineData: { mimeType: 'image/jpeg', data: base64Image } }
              ]
            }]
          },
          { headers: { 'Content-Type': 'application/json' } }
        );

        // Renamed 'caption' to 'analysis' for clarity
        const analysis = geminiResponse.data?.candidates?.[0]?.content?.parts?.[0]?.text || 'No analysis generated.';
        console.log('SUCCESS! Analysis generated:', analysis);

        res.status(200).send({ data: { analysis } });

      } catch (error) {
        const errorMessage = error.response?.data?.error?.message || error.message;
        console.error('Error inside try-catch block:', errorMessage, error.stack);
        res.status(500).send({ error: { message: `Image captioning failed: ${errorMessage}` } });
      }
    });
  }
);

console.log('Function initialization completed');
