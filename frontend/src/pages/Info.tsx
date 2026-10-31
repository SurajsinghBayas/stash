import { AiChat02Icon, Bug01Icon, Idea01Icon, Mail01Icon, UserCircleIcon } from "@hugeicons/core-free-icons";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { PageShell } from "@/components/Marketing";
import { Mascot } from "@/components/Mascot";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/primitives";
import { SITE } from "@/lib/site";

/** Readable long-form text: headings, paragraphs and lists with consistent rhythm. */
function Prose({ children }: { children: ReactNode }) {
  return (
    <div className="text-[15px] leading-[1.75] text-text-2 [&_a]:text-accent-text [&_a]:underline-offset-4 hover:[&_a]:underline
      [&_h2]:mb-3 [&_h2]:mt-12 [&_h2]:text-[20px] [&_h2]:font-semibold [&_h2]:tracking-[-0.015em] [&_h2]:text-text first:[&_h2]:mt-0
      [&_h3]:mb-2 [&_h3]:mt-6 [&_h3]:text-[16px] [&_h3]:font-semibold [&_h3]:text-text
      [&_li]:mt-1.5 [&_p]:mt-3 [&_strong]:font-semibold [&_strong]:text-text [&_ul]:mt-3 [&_ul]:list-disc [&_ul]:pl-5">
      {children}
    </div>
  );
}

const Mail = () => <a href={`mailto:${SITE.contactEmail}`}>{SITE.contactEmail}</a>;

export function About() {
  return (
    <PageShell seo={{ title: "About", path: "/about", description: "Why we built Stash: one visual canvas for everything you save, an assistant that answers from your own cards, and privacy by default." }} eyebrow="About" title="We built Stash because we kept losing things."
      lead="Twenty open tabs, a notes app, a folder of screenshots and a chat with yourself. Everything was saved; nothing could be found.">
      <Prose>
        <h2>One place for everything you save</h2>
        <p>
          Stash puts links, notes, code and images on a single visual canvas, so related things sit next to each other the
          way they do in your head. One canvas per project, course, trip or idea, laid out however you like.
        </p>
        <h2>An assistant that only knows what you saved</h2>
        <p>
          When you ask Stash a question, it answers from your own cards and points at each one it used. It does not
          browse the web and it does not make things up to fill a gap: if your cards don't have the answer, it says so.
        </p>
        <h2>Reminders that actually reach you</h2>
        <p>
          Saving something is only half the job. Stash sends a reminder to your inbox at the moment you chose, and a short
          digest of what you saved so the important bits don't sink to the bottom.
        </p>
        <h2>What we care about</h2>
        <ul>
          <li><strong>Your data is yours.</strong> Canvases are private, we never sell data, and you can delete anything.</li>
          <li><strong>Safe by default.</strong> Adult or abusive content is caught before it is shown, answered or emailed.</li>
          <li><strong>Calm software.</strong> No feeds, no streaks, no noise. Just your things, easy to find.</li>
        </ul>
      </Prose>
      <div className="mt-12 flex flex-wrap gap-3">
        <Button asChild variant="primary"><Link to="/signup">Start for free</Link></Button>
        <Button asChild variant="secondary"><Link to="/contact">Say hello</Link></Button>
      </div>
    </PageShell>
  );
}

const TOPICS = [
  { icon: AiChat02Icon, title: "Questions about Stash", body: "How something works, or whether Stash fits what you need." },
  { icon: Bug01Icon, title: "Report a problem", body: "Tell us what you did and what happened. A screenshot helps." },
  { icon: Idea01Icon, title: "Ideas and feedback", body: "Features you would love to see, or things that get in your way." },
  { icon: UserCircleIcon, title: "Your account and data", body: "Access, export or deletion of your account and everything in it." },
];

export function Contact() {
  return (
    <PageShell seo={{ title: "Contact", path: "/contact", description: "Questions, feedback, account or privacy requests: how to reach the people behind Stash." }} eyebrow="Contact" title="Get in touch."
      lead="Questions, bugs, ideas or account requests. A real person reads every message, usually within two working days.">
      <a href={`mailto:${SITE.contactEmail}`}
        className="flex items-center gap-4 rounded-[16px] border border-border bg-surface p-6 transition-colors hover:bg-surface-2">
        <span className="grid size-11 place-items-center rounded-[12px] bg-accent-soft text-accent-text"><Icon icon={Mail01Icon} size={22} /></span>
        <span>
          <span className="block text-[13px] text-text-3">Email us</span>
          <span className="block text-[17px] font-semibold">{SITE.contactEmail}</span>
        </span>
      </a>
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        {TOPICS.map((t) => (
          <div key={t.title} className="rounded-[14px] border border-border bg-surface p-5">
            <Icon icon={t.icon} size={18} className="text-accent-text" />
            <h2 className="mt-3 text-[15px] font-semibold">{t.title}</h2>
            <p className="mt-1 text-[13.5px] leading-relaxed text-text-2">{t.body}</p>
          </div>
        ))}
      </div>
      <p className="mt-8 text-[14px] text-text-2">
        Looking for a quick answer? The <Link to="/#faq" className="text-accent-text underline-offset-4 hover:underline">FAQ</Link> covers
        the most common questions.
      </p>
    </PageShell>
  );
}

export function Privacy() {
  return (
    <PageShell seo={{ title: "Privacy policy", path: "/privacy", description: "What Stash collects, why, how long it is kept, and how to export or delete your data." }} eyebrow="Legal" title="Privacy policy" lead={<p>Last updated {SITE.legalUpdated}. This page explains what Stash collects, why, and the choices you have.</p>}>
      <Prose>
        <h2>The short version</h2>
        <ul>
          <li>We collect what we need to run Stash: your account details and the cards you save.</li>
          <li>Your canvases are private to your account unless you create a share link. We never sell your data and we don't show ads.</li>
          <li>AI features process your cards only to answer your questions, summarise them for you and keep them searchable.</li>
          <li>You can delete any card or canvas at any time, export everything, and delete your whole account from Settings.</li>
        </ul>

        <h2>What we collect</h2>
        <h3>Account information</h3>
        <p>
          Your email address and a securely hashed password if you sign up with email. If you sign in with Google or X, we
          receive your name, email address (when the provider shares it) and profile picture from that provider. We also
          keep your settings, such as time zone and email preferences.
        </p>
        <h3>Your content</h3>
        <p>
          The cards you create: links and the page details we fetch for them, notes, text, code, images you upload, their
          positions on your canvases, earlier versions of edited cards, reminders, and the questions you ask the assistant
          together with its answers. If you use save by email, we receive the emails you send to your Stash address and
          keep their links and text as cards.
        </p>
        <h3>Facts the assistant remembers</h3>
        <p>
          If memory is on, Stash keeps a few short facts from your chats, such as how you like answers written. You can
          see every fact in Settings, delete any of them, or turn memory off.
        </p>
        <h3>Technical information</h3>
        <p>
          Basic logs needed to keep the service secure and working, such as request times, error reports and IP addresses
          used for rate limiting. We use only essential cookies to keep you signed in. There are no advertising or
          third-party tracking cookies.
        </p>

        <h2>How we use it</h2>
        <ul>
          <li>To provide Stash: store your canvases, show link previews, and keep your cards searchable.</li>
          <li>To power the assistant: find the cards relevant to your question and write an answer from them.</li>
          <li>To send the emails you asked for: verification, password resets, reminders and digests.</li>
          <li>To keep Stash safe: check content for adult or abusive material and prevent abuse of the service.</li>
          <li>To fix problems and improve the product.</li>
        </ul>
        <p>We don't use your cards to train our own AI models, and we don't sell or rent your personal data to anyone.</p>

        <h2>Shared canvases</h2>
        <p>
          If you create a share link for a canvas, anyone with the link can view that canvas without signing in. They see
          its cards (except ones the safety check hid or hasn't finished), but not your name, email, reminders, chats or
          other canvases. You can stop sharing at any time, and the old link stops working at once.
        </p>

        <h2>Who processes your data</h2>
        <p>
          We rely on trusted service providers to run Stash: cloud hosting and storage, AI model providers that process
          your content to answer questions and create summaries, and an email delivery service. They process data on our
          behalf only to provide their service. Your account and content are stored in India; some of these providers may
          process data in other countries.
        </p>

        <h2>How long we keep it</h2>
        <p>
          We keep your content for as long as your account exists. Deleted cards and canvases disappear from your
          searches and the assistant right away and move to Recently deleted, where you can restore them for 30 days.
          After 30 days they are erased for good, along with their images and history. Deleting your account erases the
          account and all of its content right away. Logs are kept for a limited time for security.
        </p>

        <h2>Your choices and rights</h2>
        <ul>
          <li>Edit or delete any card, canvas or reminder at any time.</li>
          <li>Turn digests and reminder emails off in Settings, or with the one-click link in every email.</li>
          <li>View, delete or turn off what the assistant remembers.</li>
          <li>Download a copy of all your data from Settings → Your data.</li>
          <li>Delete your account and all its content from Settings → Your data, or by emailing <Mail />.</li>
        </ul>

        <h2>Security</h2>
        <p>
          Connections are encrypted with HTTPS, passwords are stored as one-way hashes, sessions use secure cookies, and
          uploaded images are kept in private storage. No system is perfectly secure, but we work hard to protect your data.
        </p>

        <h2>Children</h2>
        <p>Stash is not intended for children under 13, and we don't knowingly collect their data.</p>

        <h2>Changes</h2>
        <p>
          If we change this policy, we will update the date at the top, and tell you by email or in the app if the change is
          significant.
        </p>

        <h2>Contact</h2>
        <p>Questions about privacy? Email <Mail />.</p>
      </Prose>
    </PageShell>
  );
}

export function Terms() {
  return (
    <PageShell seo={{ title: "Terms of service", path: "/terms", description: "The terms for using Stash, including acceptable use and your content." }} eyebrow="Legal" title="Terms of service" lead={<p>Last updated {SITE.legalUpdated}. By using Stash you agree to these terms.</p>}>
      <Prose>
        <h2>Your account</h2>
        <p>
          You need an account to use Stash. Keep your sign-in details safe and tell us if you think someone else has access
          to your account. You must be at least 13 years old to use Stash.
        </p>

        <h2>Your content</h2>
        <p>
          You own what you save in Stash. You give us permission to store, process and display it only so we can run the
          service for you, including making it searchable, generating previews and summaries, and answering your questions.
          You are responsible for having the right to save what you upload.
        </p>

        <h2>Acceptable use</h2>
        <p>Don't use Stash to:</p>
        <ul>
          <li>store or share sexual content, content involving minors, harassment, hate speech or threats of violence;</li>
          <li>break the law or infringe anyone's rights;</li>
          <li>attack, overload or try to get around the limits or security of the service;</li>
          <li>access other people's accounts or data.</li>
        </ul>
        <p>
          Content that breaks these rules may be blocked, hidden from the assistant or removed, and accounts that repeatedly
          break them may be suspended.
        </p>

        <h2>The assistant</h2>
        <p>
          Answers are generated automatically from your cards and can be incomplete or wrong. Check anything important
          against the cards it cites before you rely on it.
        </p>

        <h2>Free plan and limits</h2>
        <p>
          Stash is currently free. Each account has a monthly assistant allowance and image storage limit, shown in
          Settings. We may change these limits, and if we introduce paid plans we will tell you in advance.
        </p>

        <h2>Availability</h2>
        <p>
          We work to keep Stash available and your data safe, but the service is provided "as is", without guarantees that
          it will always be available or error-free. Keep your own copy of anything you can't afford to lose.
        </p>

        <h2>Ending your use</h2>
        <p>
          You can stop using Stash at any time and delete your account from Settings. We may suspend or close accounts that break
          these terms or put the service or other users at risk.
        </p>

        <h2>Liability</h2>
        <p>
          To the extent the law allows, Stash is not liable for indirect or consequential losses, or for loss of data,
          arising from your use of the service.
        </p>

        <h2>Changes</h2>
        <p>
          We may update these terms. We will change the date at the top, and tell you by email or in the app if the change is
          significant. Continuing to use Stash after a change means you accept the updated terms.
        </p>

        <h2>Contact</h2>
        <p>Questions about these terms? Email <Mail />.</p>
      </Prose>
      <div className="mt-12 flex items-center gap-3 text-[13px] text-text-3">
        <Mascot size={22} state="sleeping" /> Thanks for reading the fine print.
      </div>
    </PageShell>
  );
}
