import LegalPage from "./LegalPage";

const SECTIONS = [
  {
    heading: "1. Acceptance of Terms",
    body: [
      "By accessing or using Chatpaper ('the Service'), you agree to be bound by these Terms of Service ('Terms'). If you do not agree to these Terms, please do not use the Service.",
      "Chatpaper reserves the right to update or modify these Terms at any time without prior notice. Your continued use of the Service following any changes constitutes your acceptance of the revised Terms.",
    ],
  },
  {
    heading: "2. Description of Service",
    body: [
      "Chatpaper is an AI-powered document analysis tool that allows users to upload documents and interact with them through a conversational interface. The Service uses large language models (LLMs) and retrieval-augmented generation (RAG) to answer questions about uploaded documents.",
      "The Service currently supports PDF, DOCX, TXT, CSV, and XLSX file formats.",
    ],
  },
  {
    heading: "3. User Accounts",
    body: [
      "You must create an account to use Chatpaper. You are responsible for maintaining the confidentiality of your account credentials and for all activity that occurs under your account.",
      "You must provide accurate, current, and complete information when creating your account. You agree to update this information to keep it accurate.",
      "You may not share your account credentials with any third party. You must notify us immediately at support@chatpaper.ai if you suspect any unauthorized use of your account.",
    ],
  },
  {
    heading: "4. User Content and Data",
    body: [
      "You retain ownership of all documents and content you upload to Chatpaper ('User Content'). By uploading documents, you grant Chatpaper a limited, non-exclusive license to process your content solely for the purpose of providing the Service.",
      "Chatpaper does not sell, share, or otherwise distribute your User Content to third parties, except as required by law or as necessary to provide the Service (e.g., sending text to OpenAI's API for processing).",
      "You are solely responsible for the legality, accuracy, and appropriateness of all User Content you upload. Do not upload documents containing sensitive personal data, confidential information belonging to third parties, or content that violates applicable laws.",
    ],
  },
  {
    heading: "5. Acceptable Use",
    body: [
      "You agree not to use the Service to: (a) violate any applicable laws or regulations; (b) infringe the intellectual property rights of others; (c) upload malicious files or attempt to compromise the security of the Service; (d) reverse engineer, decompile, or attempt to extract the source code of the Service; (e) use the Service for any unlawful, harmful, or fraudulent purpose.",
      "We reserve the right to suspend or terminate accounts that violate these acceptable use guidelines.",
    ],
  },
  {
    heading: "6. AI-Generated Responses",
    body: [
      "Chatpaper uses artificial intelligence to generate responses. AI responses may not always be accurate, complete, or up to date. You should independently verify any information provided by the Service before relying on it for important decisions.",
      "Chatpaper does not warrant the accuracy, reliability, or completeness of any AI-generated content and accepts no liability for decisions made based on such content.",
    ],
  },
  {
    heading: "7. Intellectual Property",
    body: [
      "The Chatpaper name, logo, software, and all related materials are the intellectual property of Chatpaper and are protected by applicable copyright, trademark, and other intellectual property laws.",
      "You may not copy, modify, distribute, or create derivative works based on the Service without explicit written permission.",
    ],
  },
  {
    heading: "8. Disclaimer of Warranties",
    body: [
      "THE SERVICE IS PROVIDED 'AS IS' AND 'AS AVAILABLE' WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.",
      "Chatpaper does not warrant that the Service will be uninterrupted, error-free, or free of viruses or other harmful components.",
    ],
  },
  {
    heading: "9. Limitation of Liability",
    body: [
      "TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, CHATPAPER SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES ARISING OUT OF OR RELATED TO YOUR USE OF THE SERVICE.",
      "IN NO EVENT SHALL CHATPAPER'S TOTAL LIABILITY EXCEED THE GREATER OF (A) THE AMOUNT YOU PAID TO USE THE SERVICE IN THE TWELVE MONTHS PRECEDING THE CLAIM, OR (B) ONE HUNDRED DOLLARS ($100).",
    ],
  },
  {
    heading: "10. Termination",
    body: [
      "You may stop using the Service at any time by deleting your account. We may suspend or terminate your access to the Service at any time for any reason, including violation of these Terms.",
      "Upon termination, your right to use the Service ceases immediately. We may retain your account data for a reasonable period before deletion, as permitted by applicable law.",
    ],
  },
  {
    heading: "11. Governing Law",
    body: [
      "These Terms shall be governed by and construed in accordance with applicable laws. Any dispute arising under these Terms shall be resolved through binding arbitration or in courts of competent jurisdiction.",
    ],
  },
  {
    heading: "12. Contact Us",
    body: [
      "If you have any questions about these Terms of Service, please contact us at support@chatpaper.ai.",
    ],
  },
];

function TermsOfService() {
  return (
    <LegalPage
      title="Terms of Service"
      subtitle="Please read these terms carefully before using Chatpaper."
      lastUpdated="June 2026"
      sections={SECTIONS}
    />
  );
}

export default TermsOfService;
