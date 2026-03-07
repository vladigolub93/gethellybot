import {
  CandidateSalaryCurrency,
  CandidateSalaryPeriod,
  CandidateWorkMode,
} from "../shared/types/state.types";
import { UsersRepository } from "../db/repositories/users.repo";

export interface CandidateMandatoryFields {
  country: string;
  city: string;
  workMode: CandidateWorkMode | null;
  salaryAmount: number | null;
  salaryCurrency: CandidateSalaryCurrency | null;
  salaryPeriod: CandidateSalaryPeriod | null;
  profileComplete: boolean;
}

export class CandidateMandatoryFieldsService {
  constructor(private readonly usersRepository: UsersRepository) {}

  async evaluateCandidateCompleteness(userId: number): Promise<boolean> {
    const profile = await this.usersRepository.getCandidateMandatoryFields(userId);
    return profile.profileComplete;
  }

  async getMandatoryFields(userId: number): Promise<CandidateMandatoryFields> {
    return this.usersRepository.getCandidateMandatoryFields(userId);
  }

  async saveLocation(
    userId: number,
    input: {
      country: string;
      city: string;
    },
  ): Promise<CandidateMandatoryFields> {
    await this.usersRepository.upsertCandidateMandatoryFields({
      telegramUserId: userId,
      country: input.country,
      city: input.city,
    });
    return this.usersRepository.getCandidateMandatoryFields(userId);
  }

  async saveWorkMode(
    userId: number,
    workMode: CandidateWorkMode,
  ): Promise<CandidateMandatoryFields> {
    await this.usersRepository.upsertCandidateMandatoryFields({
      telegramUserId: userId,
      workMode,
    });
    return this.usersRepository.getCandidateMandatoryFields(userId);
  }

  async saveSalary(
    userId: number,
    input: {
      amount: number;
      currency: CandidateSalaryCurrency;
      period: CandidateSalaryPeriod;
    },
  ): Promise<CandidateMandatoryFields> {
    await this.usersRepository.upsertCandidateMandatoryFields({
      telegramUserId: userId,
      salaryAmount: input.amount,
      salaryCurrency: input.currency,
      salaryPeriod: input.period,
    });
    return this.usersRepository.getCandidateMandatoryFields(userId);
  }
}
