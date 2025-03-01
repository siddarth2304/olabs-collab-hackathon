    import { db } from "./firebase-config.js";
    import { doc, onSnapshot, setDoc } from "https://www.gstatic.com/firebasejs/11.4.0/firebase-firestore.js";

    let editor;

    require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.38.0/min/vs' } });

    require(['vs/editor/editor.main'], function () {
        editor = monaco.editor.create(document.getElementById('editor'), {
            value: "# Welcome to OLabs Collab!",
            language: "python",
            theme: "vs-dark",
            automaticLayout: true
        });

        const docRef = doc(db, "sessions", "default");

        onSnapshot(docRef, (docSnap) => {
            if (docSnap.exists() && docSnap.data().code !== editor.getValue()) {
                editor.setValue(docSnap.data().code);
            }
        });

        editor.onDidChangeModelContent(() => {
            setDoc(docRef, { code: editor.getValue() }, { merge: true });
        });
    });
