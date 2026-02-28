import { JobsRepository } from "../db/repositories/jobs.repo";
import { JobBudgetCurrency, JobBudgetPeriod, JobWorkFormat } from "../shared/types/state.types";

export interface JobMandatoryFields {
  workFormat: JobWorkFormat | null;
  remoteCountries: string[];
  remoteWorldwide: boolean;
  budgetMin: number | null;
  budgetMax: number | null;
  budgetCurrency: JobBudgetCurrency | null;
  budgetPeriod: JobBudgetPeriod | null;
  profileComplete: boolean;
}

export class JobMandatoryFieldsService {
  constructor(private readonly jobsRepository: JobsRepository) {}

  async getMandatoryFields(managerTelegramUserId: number): Promise<JobMandatoryFields> {
    return this.jobsRepository.getJobMandatoryFields(managerTelegramUserId);
  }

  async saveWorkFormat(
    managerTelegramUserId: number,
    workFormat: JobWorkFormat,
  ): Promise<void> {
    await this.jobsRepository.upsertJobMandatoryFields({
      managerTelegramUserId,
      workFormat,
      remoteWorldwide: workFormat === "remote" ? false : false,
      remoteCountries: workFormat === "remote" ? [] : [],
    });
  }

  async saveCountries(
    managerTelegramUserId: number,
    input: {
      worldwide: boolean;
      countries: string[];
    },
  ): Promise<void> {
    await this.jobsRepository.upsertJobMandatoryFields({
      managerTelegramUserId,
      remoteWorldwide: input.worldwide,
      remoteCountries: input.countries,
    });
  }

  async saveBudget(
    managerTelegramUserId: number,
    input: {
      min: number;
      max: number;
      currency: JobBudgetCurrency;
      period: JobBudgetPeriod;
    },
  ): Promise<void> {
    await this.jobsRepository.upsertJobMandatoryFields({
      managerTelegramUserId,
      budgetMin: input.min,
      budgetMax: input.max,
      budgetCurrency: input.currency,
      budgetPeriod: input.period,
    });
  }

  async evaluateJobCompleteness(managerTelegramUserId: number): Promise<boolean> {
    return this.jobsRepository.evaluateJobCompleteness(managerTelegramUserId);
  }
}
