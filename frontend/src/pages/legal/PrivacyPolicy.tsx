import LegalPage from "./LegalPage";

const SECTIONS = [
  {
    heading: "1. Introduction",
    body: [
      "Chatpaper ('we', 'us', or 'our') is committed to protecting your privacy. This Privacy Policy explains how we collect, use, store, and share information when you use our Service.",
      "By using Chatpaper, you agree to the collection and use of information in accordance with this Privacy Policy.",
    ],
  },
  {
    heading: "2. Information We Collect",
    body: [
      "Account Information: When you register, we collect your name and email address. If you sign in with Google, we receive your name and email from Google's OAuth service.",
      "Uploaded Documents: We store the documents you upload in order to process them and provide the chat functionality. Documents are stored securely and associated only with your account.",
      "Conversation Data: We store the questions you ask and the AI-generated responses within each conversation, so you can review past conversations.",
      "Usage Data: We may collect basic usage information such as pages visited, features used, and error logs for the purpose of improving the Service.",
    ],
  },
  {
    heading: "3. How We Use Your Information",
    body: [
      "To provide the Service: We use your documents and conversation data exclusively to power the AI document-chat functionality.",
      "To communicate with you: We may use your email address to send important account notifications, such as security alerts.",
      "To improve the Service: Aggregated, anonymized usage data may be used to identify bugs, improve performance, and develop new features.",
      "We do not use your personal data for advertising purposes.",
    ],
  },
  {
    heading: "4. Third-Party Services",
    body: [
      "AI Processing (OpenAI): To generate answers, we send the relevant excerpts from your documents — not the full document — to OpenAI's API. This data is subject to OpenAI's data usage policies. We configure OpenAI API requests with data privacy settings where available.",
      "Hosting and Infrastructure: Your data is stored on servers hosted by our infrastructure providers. These providers are contractually obligated to keep your data confidential.",
      "Google OAuth: If you choose to sign in with Google, Google shares your name and email address with us under Google's OAuth terms.",
    ],
  },
  {
    heading: "5. Data Isolation and Security",
    body: [
      "Chatpaper enforces strict per-user data isolation. You can only access documents and conversations associated with your own account. We implement technical safeguards including encrypted passwords (bcrypt), JWT-based authentication, and database-level user scoping to prevent cross-user data access.",
      "We use HTTPS to encrypt data in transit. Passwords are never stored in plain text.",
      "Despite these measures, no method of electronic transmission or storage is 100% secure. We cannot guarantee absolute security.",
    ],
  },
  {
    heading: "6. Data Retention",
    body: [
      "We retain your account data, uploaded documents, and conversation history for as long as your account is active.",
      "When you delete a document or conversation, it is permanently removed from our database and vector store.",
      "When you delete your account, we will delete your data within a reasonable period, except where retention is required by law.",
    ],
  },
  {
    heading: "7. Your Rights",
    body: [
      "Depending on your location, you may have the following rights regarding your personal data: the right to access the data we hold about you; the right to request correction of inaccurate data; the right to request deletion of your data; the right to data portability.",
      "To exercise any of these rights, please contact us at support@chatpaper.ai. We will respond to your request within 30 days.",
    ],
  },
  {
    heading: "8. Children's Privacy",
    body: [
      "The Service is not directed to children under the age of 13. We do not knowingly collect personal information from children under 13. If you believe we have inadvertently collected such information, please contact us immediately.",
    ],
  },
  {
    heading: "9. Changes to This Policy",
    body: [
      "We may update this Privacy Policy from time to time. We will notify you of significant changes by posting the new policy on this page with an updated date. Your continued use of the Service after changes are posted constitutes acceptance of the revised policy.",
    ],
  },
  {
    heading: "10. Contact Us",
    body: [
      "If you have any questions or concerns about this Privacy Policy, please contact us at support@chatpaper.ai.",
    ],
  },
];

function PrivacyPolicy() {
  return (
    <LegalPage
      title="Privacy Policy"
      subtitle="Your privacy matters. Here is how we handle your data."
      lastUpdated="June 2026"
      sections={SECTIONS}
    />
  );
}

export default PrivacyPolicy;
