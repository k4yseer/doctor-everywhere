window.onload = function () {
  window.ui = SwaggerUIBundle({
    urls: [
      // ── Atomic Services ─────────────────────────────────────────────────
      { url: "/specs/doctor/apispec_1.json",         name: "Doctor Service" },
      { url: "/specs/appointment/apispec_1.json",    name: "Appointment Service" },
      { url: "/specs/patient/apispec_1.json",        name: "Patient Service" },
      { url: "/specs/payment-wrapper/apispec_1.json",name: "Payment Wrapper" },
      { url: "/specs/teleconferencing/apispec_1.json",name: "Teleconferencing Wrapper" },
      { url: "/specs/error/apispec_1.json",          name: "Error Service" },
      { url: "/specs/invoice/apispec_1.json",        name: "Invoice Service" },
      { url: "/specs/inventory/apispec.json",        name: "Inventory Service" },
      { url: "/specs/queue/apispec_1.json",          name: "Queue Service" },
      { url: "/specs/delivery/apispec_1.json",       name: "Delivery Service" },
      // ── Composite Services ───────────────────────────────────────────────
      { url: "/specs/join-queue/apispec_1.json",         name: "Join Queue (Composite)" },
      { url: "/specs/setup-consultation/apispec_1.json", name: "Setup Consultation (Composite)" },
      { url: "/specs/make-prescription/apispec_1.json",  name: "Make Prescription (Composite)" },
      { url: "/specs/make-payment/apispec_1.json",       name: "Make Payment (Composite)" },
    ],
    "urls.primaryName": "Doctor Service",
    dom_id: "#swagger-ui",
    deepLinking: true,
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
    plugins: [SwaggerUIBundle.plugins.DownloadUrl],
    layout: "StandaloneLayout",
  });
};
