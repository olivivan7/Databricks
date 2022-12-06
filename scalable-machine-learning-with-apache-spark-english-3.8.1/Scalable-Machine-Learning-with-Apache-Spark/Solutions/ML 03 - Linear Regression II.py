# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC 
# MAGIC <div style="text-align: center; line-height: 0; padding-top: 9px;">
# MAGIC   <img src="https://databricks.com/wp-content/uploads/2018/03/db-academy-rgb-1200px.png" alt="Databricks Learning" style="width: 600px">
# MAGIC </div>

# COMMAND ----------

# MAGIC %md # Linear Regression: Improving our model
# MAGIC 
# MAGIC In this notebook we will be adding additional features to our model, as well as discuss how to handle categorical features.
# MAGIC 
# MAGIC ## ![Spark Logo Tiny](https://files.training.databricks.com/images/105/logo_spark_tiny.png) In this lesson you:<br>
# MAGIC  - One Hot Encode categorical variables
# MAGIC  - Use the Pipeline API
# MAGIC  - Save and load models

# COMMAND ----------

# MAGIC %run "./Includes/Classroom-Setup"

# COMMAND ----------

file_path = f"{datasets_dir}/airbnb/sf-listings/sf-listings-2019-03-06-clean.delta/"
airbnb_df = spark.read.format("delta").load(file_path)

# COMMAND ----------

# MAGIC %md ## Train/Test Split
# MAGIC 
# MAGIC Let's use the same 80/20 split with the same seed as the previous notebook so we can compare our results apples to apples (unless you changed the cluster config!)

# COMMAND ----------

train_df, test_df = airbnb_df.randomSplit([.8, .2], seed=42)

# COMMAND ----------

# MAGIC %md ## Categorical Variables
# MAGIC 
# MAGIC There are a few ways to handle categorical features:
# MAGIC * Assign them a numeric value
# MAGIC * Create "dummy" variables (also known as One Hot Encoding)
# MAGIC * Generate embeddings (mainly used for textual data)
# MAGIC 
# MAGIC ### One Hot Encoder
# MAGIC Here, we are going to One Hot Encode (OHE) our categorical variables. Spark doesn't have a **`dummies`** function, and OHE is a two step process. First, we need to use <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.ml.feature.StringIndexer.html?highlight=stringindexer#pyspark.ml.feature.StringIndexer" target="_blank">StringIndexer</a> to map a string column of labels to an ML column of label indices.
# MAGIC 
# MAGIC Then, we can apply the <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.ml.feature.OneHotEncoder.html?highlight=onehotencoder#pyspark.ml.feature.OneHotEncoder" target="_blank">OneHotEncoder</a> to the output of the StringIndexer.

# COMMAND ----------

from pyspark.ml.feature import OneHotEncoder, StringIndexer

categorical_cols = [field for (field, dataType) in train_df.dtypes if dataType == "string"]
index_output_cols = [x + "Index" for x in categorical_cols]
ohe_output_cols = [x + "OHE" for x in categorical_cols]

string_indexer = StringIndexer(inputCols=categorical_cols, outputCols=index_output_cols, handleInvalid="skip")
ohe_encoder = OneHotEncoder(inputCols=index_output_cols, outputCols=ohe_output_cols)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Vector Assembler
# MAGIC 
# MAGIC Now we can combine our OHE categorical features with our numeric features.

# COMMAND ----------

from pyspark.ml.feature import VectorAssembler

numeric_cols = [field for (field, dataType) in train_df.dtypes if ((dataType == "double") & (field != "price"))]
assembler_inputs = ohe_output_cols + numeric_cols
vec_assembler = VectorAssembler(inputCols=assembler_inputs, outputCol="features")

# COMMAND ----------

# MAGIC %md ## Linear Regression
# MAGIC 
# MAGIC Now that we have all of our features, let's build a linear regression model.

# COMMAND ----------

from pyspark.ml.regression import LinearRegression

lr = LinearRegression(labelCol="price", featuresCol="features")

# COMMAND ----------

# MAGIC %md ## Pipeline
# MAGIC 
# MAGIC Let's put all these stages in a Pipeline. A <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.ml.Pipeline.html?highlight=pipeline#pyspark.ml.Pipeline" target="_blank">Pipeline</a> is a way of organizing all of our transformers and estimators.
# MAGIC 
# MAGIC This way, we don't have to worry about remembering the same ordering of transformations to apply to our test dataset.

# COMMAND ----------

from pyspark.ml import Pipeline

stages = [string_indexer, ohe_encoder, vec_assembler, lr]
pipeline = Pipeline(stages=stages)

pipeline_model = pipeline.fit(train_df)

# COMMAND ----------

# MAGIC %md ## Saving Models
# MAGIC 
# MAGIC We can save our models to persistent storage (e.g. DBFS) in case our cluster goes down so we don't have to recompute our results.

# COMMAND ----------

pipeline_model.write().overwrite().save(working_dir)

# COMMAND ----------

# MAGIC %md ## Loading models
# MAGIC 
# MAGIC When you load in models, you need to know the type of model you are loading back in (was it a linear regression or logistic regression model?).
# MAGIC 
# MAGIC For this reason, we recommend you always put your transformers/estimators into a Pipeline, so you can always load the generic PipelineModel back in.

# COMMAND ----------

from pyspark.ml import PipelineModel

saved_pipeline_model = PipelineModel.load(working_dir)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Apply model to test set

# COMMAND ----------

pred_df = saved_pipeline_model.transform(test_df)

display(pred_df.select("features", "price", "prediction"))

# COMMAND ----------

# MAGIC %md ## Evaluate model
# MAGIC 
# MAGIC ![](https://files.training.databricks.com/images/r2d2.jpg) How is our R2 doing? 

# COMMAND ----------

from pyspark.ml.evaluation import RegressionEvaluator

regression_evaluator = RegressionEvaluator(predictionCol="prediction", labelCol="price", metricName="rmse")

rmse = regression_evaluator.evaluate(pred_df)
r2 = regression_evaluator.setMetricName("r2").evaluate(pred_df)
print(f"RMSE is {rmse}")
print(f"R2 is {r2}")

# COMMAND ----------

# MAGIC %md As you can see, our RMSE decreased when compared to the model without one-hot encoding, and the R2 increased as well!

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC &copy; 2022 Databricks, Inc. All rights reserved.<br/>
# MAGIC Apache, Apache Spark, Spark and the Spark logo are trademarks of the <a href="https://www.apache.org/">Apache Software Foundation</a>.<br/>
# MAGIC <br/>
# MAGIC <a href="https://databricks.com/privacy-policy">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use">Terms of Use</a> | <a href="https://help.databricks.com/">Support</a>
