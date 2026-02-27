import { MatchRecord } from "./match.types";
import { StateService } from "../state/state.service";

interface ContactExchangeResult {
  managerContact: string;
  candidateContact: string;
}

export class ContactExchangeService {
  constructor(private readonly stateService: StateService) {}

  buildContacts(match: MatchRecord): ContactExchangeResult {
    const managerSession = this.stateService.getSession(match.managerUserId);
    const candidateSession = this.stateService.getSession(match.candidateUserId);

    const managerContact = managerSession?.username
      ? `@${managerSession.username}`
      : `user #${match.managerUserId}`;
    const candidateContact = candidateSession?.username
      ? `@${candidateSession.username}`
      : `user #${match.candidateUserId}`;

    return {
      managerContact,
      candidateContact,
    };
  }
}
