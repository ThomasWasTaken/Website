document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;
  const menuToggle = document.querySelector("[data-menu-toggle]");
  const navMenu = document.querySelector("[data-nav-menu]");
  const dropdowns = document.querySelectorAll("[data-dropdown]");
  const faqItems = document.querySelectorAll(".faq-item");
  const trackedScrollMilestones = new Set();
  const trackedSectionViews = new Set();
  const userStorageKey = "legal_site_user_id";

  const endpoint = (() => {
    if (body.dataset.trackEndpoint) return body.dataset.trackEndpoint;
    if (window.location.protocol === "http:" || window.location.protocol === "https:") {
      return `${window.location.origin}/api/track/`;
    }
    return "http://127.0.0.1:8000/api/track/";
  })();

  const getSourceChannel = () => {
    const params = new URLSearchParams(window.location.search);
    const explicitChannel = (
      params.get("channel_id")
      || params.get("source_channel")
      || params.get("utm_source")
      || body.dataset.sourceChannel
    );
    if (explicitChannel) return explicitChannel.trim();

    if (document.referrer) {
      try {
        const refHost = new URL(document.referrer).hostname.replace(/^www\./, "");
        if (refHost) return `ref:${refHost}`;
      } catch (error) {
        // Ignore malformed referrers and fall back to direct.
      }
    }
    return "direct";
  };

  const sourceChannel = getSourceChannel();
  window.__agentSourceChannel = sourceChannel;
  const trackingParams = (() => {
    const urlParams = new URLSearchParams(window.location.search);
    const params = new URLSearchParams();
    const channelId = urlParams.get("channel_id");
    const sourceChannelParam = urlParams.get("source_channel");
    const utmSource = urlParams.get("utm_source");

    if (channelId) params.set("channel_id", channelId);
    if (sourceChannelParam) params.set("source_channel", sourceChannelParam);
    if (utmSource) params.set("utm_source", utmSource);

    if (!params.get("channel_id") && sourceChannel) {
      params.set("channel_id", sourceChannel);
    }
    return params;
  })();

  const appendTrackingParamsToInternalLinks = () => {
    if (!trackingParams.toString()) return;
    document.querySelectorAll("a[href]").forEach(link => {
      const href = link.getAttribute("href");
      if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) return;
      let url;
      try {
        url = new URL(href, window.location.origin);
      } catch (error) {
        return;
      }
      if (url.origin !== window.location.origin) return;
      trackingParams.forEach((value, key) => {
        if (!url.searchParams.get(key)) {
          url.searchParams.set(key, value);
        }
      });
      link.setAttribute("href", `${url.pathname}${url.search}${url.hash}`);
    });
  };

  appendTrackingParamsToInternalLinks();

  document.querySelectorAll("a[href^='#']").forEach(anchor => {
    anchor.addEventListener("click", event => {
      const href = anchor.getAttribute("href") || "";
      if (!href || href === "#") return;
      const target = document.querySelector(href);
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  document.querySelectorAll("button[data-href]").forEach(button => {
    button.addEventListener("click", () => {
      const href = button.dataset.href;
      if (!href) return;
      window.location.assign(href);
    });
  });

  const getUserId = () => {
    const existing = window.localStorage.getItem(userStorageKey);
    if (existing) return existing;
    const created = `user-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    window.localStorage.setItem(userStorageKey, created);
    return created;
  };

  const pageSessionId = `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  const stableUserId = getUserId();
  window.__agentUserId = stableUserId;
  window.__agentSessionId = pageSessionId;

  const sendTrackingEvent = payload => {
    const payloadMetadata = payload.metadata || {};
    const eventPayload = {
      user_id: stableUserId,
      session_id: pageSessionId,
      url: window.location.href,
      referrer: document.referrer,
      metadata: {
        source_channel: sourceChannel,
        ...payloadMetadata,
      },
      ...payload
    };

    if (navigator.sendBeacon) {
      const blob = new Blob([JSON.stringify(eventPayload)], { type: "application/json" });
      navigator.sendBeacon(endpoint, blob);
      return;
    }

    fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(eventPayload),
      keepalive: true
    }).catch(() => {});
  };
  window.__agentTrack = sendTrackingEvent;

  if (menuToggle && navMenu) {
    menuToggle.addEventListener("click", () => {
      const isOpen = navMenu.classList.toggle("is-open");
      body.classList.toggle("menu-open", isOpen);
      menuToggle.setAttribute("aria-expanded", String(isOpen));
    });
  }

  dropdowns.forEach(dropdown => {
    const trigger = dropdown.querySelector("[data-dropdown-trigger]");
    if (!trigger) return;

    trigger.addEventListener("click", event => {
      if (window.innerWidth > 780) return;
      event.preventDefault();
      dropdown.classList.toggle("is-open");
    });
  });

  faqItems.forEach(item => {
    item.addEventListener("toggle", () => {
      if (!item.open) return;
      faqItems.forEach(other => {
        if (other !== item) other.open = false;
      });
    });
  });

  const navActions = document.querySelector(".nav-actions");
  if (navActions && !navActions.querySelector("[data-agent-action='nav_website']")) {
    const websiteButton = document.createElement("a");
    websiteButton.className = "btn btn-ghost";
    websiteButton.href = "../../index_light.html";
    websiteButton.textContent = "Website";
    websiteButton.dataset.agentAction = "nav_website";
    websiteButton.dataset.agentService = body.dataset.agentPage || "unknown";
    navActions.prepend(websiteButton);
  }

  const sectionObserver = new IntersectionObserver(
    entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const sectionNode = entry.target;
        const sectionName = sectionNode.dataset.agentSection;
        if (!sectionName || trackedSectionViews.has(sectionName)) return;
        trackedSectionViews.add(sectionName);
        sendTrackingEvent({
          page: body.dataset.agentPage || "unknown",
          step: body.dataset.agentStep || "landing",
          section: sectionName,
          action: "section_view",
          service: body.dataset.agentPage || "unknown",
          target: sectionName,
          metadata: {
            funnel_step: `view_${sectionName}`,
            event_category: "funnel_progress",
          },
        });
      });
    },
    { threshold: 0.45 }
  );

  document.querySelectorAll("[data-agent-section]").forEach(node => sectionObserver.observe(node));

  const trackScrollMilestone = () => {
    const doc = document.documentElement;
    const scrollHeight = doc.scrollHeight - window.innerHeight;
    if (scrollHeight <= 0) return;
    const progress = Math.round((window.scrollY / scrollHeight) * 100);
    const milestones = [25, 50, 75, 90];
    milestones.forEach(mark => {
      if (progress < mark || trackedScrollMilestones.has(mark)) return;
      trackedScrollMilestones.add(mark);
      sendTrackingEvent({
        page: body.dataset.agentPage || "unknown",
        step: body.dataset.agentStep || "landing",
        section: "engagement",
        action: "scroll_depth",
        service: body.dataset.agentPage || "unknown",
        target: `${mark}%`,
        metadata: {
          funnel_step: `scroll_${mark}`,
          event_category: "engagement",
          scroll_percent: mark,
        },
      });
    });
  };

  window.addEventListener("scroll", trackScrollMilestone, { passive: true });

  sendTrackingEvent({
    page: body.dataset.agentPage || "unknown",
    step: body.dataset.agentStep || "landing",
    section: "page",
    action: "page_view",
    service: body.dataset.agentPage || "unknown",
    target: window.location.pathname
  });

  document.querySelectorAll("[data-agent-action]").forEach(element => {
    element.addEventListener("click", () => {
      const sectionNode = element.closest("[data-agent-section]");
      const detail = {
        page: body.dataset.agentPage || "unknown",
        step: body.dataset.agentStep || "unknown",
        section: sectionNode ? sectionNode.dataset.agentSection : "global",
        action: element.dataset.agentAction || "unknown",
        service: element.dataset.agentService || body.dataset.agentPage || "unknown",
        target: element.getAttribute("href") || element.getAttribute("type") || "unknown"
      };

      window.dispatchEvent(new CustomEvent("agent:track", { detail }));
      window.__agentViewQueue = window.__agentViewQueue || [];
      window.__agentViewQueue.push(detail);
      sendTrackingEvent(detail);
    });
  });

  document.querySelectorAll("a.btn, button.btn").forEach(element => {
    if (element.dataset.agentAction) return;
    element.addEventListener("click", () => {
      const sectionNode = element.closest("[data-agent-section]");
      sendTrackingEvent({
        page: body.dataset.agentPage || "unknown",
        step: body.dataset.agentStep || "unknown",
        section: sectionNode ? sectionNode.dataset.agentSection : "global",
        action: "button_click",
        service: body.dataset.agentPage || "unknown",
        target: element.getAttribute("href") || element.textContent?.trim() || "button",
      });
    });
  });
});
