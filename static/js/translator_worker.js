import { env, pipeline } from 'https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2/dist/transformers.min.js';

const TRANSLATION_MODEL = 'Xenova/nllb-200-distilled-600M';
let translator = null;
let isInitializing = false;

// Force remote Hugging Face model loading and avoid local /models path checks.
// This is important for deployments like Koyeb where local model files are not hosted.
env.allowRemoteModels = true;
env.allowLocalModels = false;
env.useBrowserCache = true;
env.useFS = false;

const defaultTranslatorOptions = {
    revision: 'main',
    local_files_only: false,
};

self.onmessage = async (event) => {
    const { text, src_lang, tgt_lang, targetId } = event.data;

    console.log('🔄 Worker received message for:', targetId, 'Text length:', text.length);

    try {
        if (!translator && !isInitializing) {
            console.log('🚀 Initializing NLLB translator model...');
            isInitializing = true;
            const startTime = Date.now();

            // Add timeout for model loading (2 minutes)
            const modelLoadPromise = pipeline('translation', TRANSLATION_MODEL, defaultTranslatorOptions);
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => reject(new Error('Model loading timeout after 2 minutes')), 120000);
            });

            translator = await Promise.race([modelLoadPromise, timeoutPromise]);

            const loadTime = Date.now() - startTime;
            console.log('✅ Model loaded successfully in', loadTime, 'ms');
            isInitializing = false;
        } else if (isInitializing) {
            console.log('⏳ Model still initializing, waiting...');
            // Wait for initialization to complete
            while (isInitializing) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
        }

        console.log('🔄 Starting translation:', src_lang, '->', tgt_lang);
        const translateStartTime = Date.now();

        // Add timeout for translation (30 seconds)
        const translatePromise = translator(text, {
            src_lang: src_lang,
            tgt_lang: tgt_lang,
        });
        const translateTimeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('Translation timeout after 30 seconds')), 30000);
        });

        const output = await Promise.race([translatePromise, translateTimeoutPromise]);

        const translateTime = Date.now() - translateStartTime;
        console.log('✅ Translation completed in', translateTime, 'ms');

        const translatedText = output[0].translation_text;
        console.log('📝 Result:', translatedText.substring(0, 100) + (translatedText.length > 100 ? '...' : ''));

        self.postMessage({
            targetId,
            translatedText: translatedText,
        });
    } catch (error) {
        console.error('❌ Translation error for', targetId, ':', error);
        self.postMessage({
            targetId,
            error: error.message || String(error),
        });
    }
};
