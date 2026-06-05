declare module "mammoth/mammoth.browser.js" {
  interface ConvertResult {
    value: string;
    messages: unknown[];
  }
  function convertToHtml(input: { arrayBuffer: ArrayBuffer }): Promise<ConvertResult>;
  export { convertToHtml };
}
